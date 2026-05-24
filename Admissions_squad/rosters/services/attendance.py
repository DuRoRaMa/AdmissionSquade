import secrets

from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from rosters.models import AttendanceActionLog, QrToken, ScheduleRecord
from rosters.services.attendance_status import (
    STATUS_ABSENT,
    STATUS_ATTENDED,
    STATUS_CANCELLED,
    sync_entry_attendance_status,
)


TOKEN_TTL = timedelta(minutes=3)
CHECKOUT_DELAY = timedelta(hours=7, minutes=0)
CHECKOUT_LATEST_TIME = time(hour=16, minute=30)


class QrNotAvailableError(ValueError):
    def __init__(self, message, available_at, seconds_left):
        super().__init__(message)
        self.available_at = available_at
        self.seconds_left = seconds_left


def _make_aware(dt):
    if timezone.is_aware(dt):
        return dt

    return timezone.make_aware(dt, timezone.get_current_timezone())


def _datetime_for_entry_date(entry, time_value):
    return _make_aware(datetime.combine(entry.date, time_value))


def _get_user_full_name(user):
    if not user:
        return ""

    return f"{user.last_name} {user.first_name} {user.middle_name}".strip() or user.email


def _get_entry_with_related(entry_id, entry_model):
    return (
        entry_model.objects
        .select_related(
            "membership",
            "membership__user",
            "work_block",
            "schedule",
            "schedule__squad",
        )
        .get(pk=entry_id)
    )


def _get_locked_record(entry):
    record, _ = (
        ScheduleRecord.objects
        .select_for_update(of=("self",))
        .get_or_create(entry_id=entry.id)
    )

    return record


def _invalidate_active_tokens(entry, action=None):
    queryset = QrToken.objects.filter(
        entry=entry,
        is_used=False,
        expires_at__gt=timezone.now(),
    )

    if action:
        queryset = queryset.filter(action=action)

    queryset.update(is_used=True)


def _create_attendance_log(entry, action, scanned_by):
    AttendanceActionLog.objects.create(
        entry=entry,
        action=action,
        scanned_by=scanned_by,
    )

def _ensure_entry_is_today(entry):
    today = timezone.localdate()

    if entry.date < today:
        raise ValueError("Смена уже прошла. QR-код недоступен.")

    if entry.date > today:
        raise ValueError("QR-код будет доступен только в день смены.")

def _build_success_response(message, action, entry, record):
    user = entry.membership.user if entry.membership else None

    return {
        "message": message,
        "action": action,
        "entry": {
            "id": entry.id,
            "date": entry.date,
            "status": entry.status,
            "status_label": entry.get_status_display(),
            "starts_at": entry.starts_at,
            "ends_at": entry.ends_at,
            "member_name": _get_user_full_name(user),
            "work_block_name": entry.work_block.name if entry.work_block else "",
        },
        "record": {
            "checked_in_at": record.checked_in_at,
            "checked_out_at": record.checked_out_at,
        },
    }


def get_checkout_available_at(entry, record):
    """
    QR-код для ухода становится доступен:
    - через 6 часов 30 минут после прихода;
    - но не позже 16:30 этого же дня.

    То есть берём минимальное из двух значений.
    """
    if not record.checked_in_at:
        return None

    by_duration = record.checked_in_at + CHECKOUT_DELAY
    by_deadline = _datetime_for_entry_date(entry, CHECKOUT_LATEST_TIME)

    available_at = min(by_duration, by_deadline)

    # Если участник пришёл после 16:30, не возвращаем время в прошлом.
    # В этом случае уход становится доступен сразу после прихода.
    if available_at < record.checked_in_at:
        return record.checked_in_at

    return available_at


def get_next_qr_action(record):
    if not record.checked_in_at:
        return QrToken.ACTION_CHECK_IN

    if not record.checked_out_at:
        return QrToken.ACTION_CHECK_OUT

    return None


@transaction.atomic
def create_qr_token(entry):
    record = _get_locked_record(entry)

    _ensure_entry_is_today(entry)

    sync_entry_attendance_status(entry, record)

    if entry.status in {STATUS_ATTENDED, STATUS_ABSENT, STATUS_CANCELLED}:
        raise ValueError("Для этой смены QR-код больше недоступен.")
    
    action = get_next_qr_action(record)

    if not action:
        raise ValueError("Смена уже полностью отмечена.")

    now = timezone.now()

    if action == QrToken.ACTION_CHECK_OUT:
        available_at = get_checkout_available_at(entry, record)

        if available_at and now < available_at:
            seconds_left = int((available_at - now).total_seconds())

            raise QrNotAvailableError(
                "QR-код для ухода пока недоступен.",
                available_at=available_at,
                seconds_left=seconds_left,
            )

    # Делаем предыдущие активные QR этого же действия недействительными.
    _invalidate_active_tokens(entry, action=action)

    return QrToken.objects.create(
        entry=entry,
        action=action,
        token=secrets.token_urlsafe(32),
        expires_at=now + TOKEN_TTL,
        is_used=False,
    )


@transaction.atomic
def scan_qr(token_value, scanned_by):
    token = (
        QrToken.objects
        .select_for_update(of=("self",))
        .filter(token=token_value)
        .first()
    )

    if not token:
        raise ValueError("QR-токен не найден.")

    if token.is_used:
        raise ValueError("QR-код уже был использован.")

    if token.is_expired():
        raise ValueError("Срок действия QR-кода истёк.")

    entry = _get_entry_with_related(
        entry_id=token.entry_id,
        entry_model=token.entry.__class__,
    )

    record = _get_locked_record(entry)

    now = timezone.now()

    if token.action == QrToken.ACTION_CHECK_IN:
        if record.checked_in_at:
            raise ValueError("Приход по этой смене уже зафиксирован.")

        record.checked_in_at = now
        record.checked_in_by = scanned_by
        record.save(update_fields=["checked_in_at", "checked_in_by"])
        sync_entry_attendance_status(entry, record)
        message = "Приход зафиксирован."

    elif token.action == QrToken.ACTION_CHECK_OUT:
        if not record.checked_in_at:
            raise ValueError("Нельзя зафиксировать уход до прихода.")

        if record.checked_out_at:
            raise ValueError("Уход по этой смене уже зафиксирован.")

        available_at = get_checkout_available_at(entry, record)

        if available_at and now < available_at:
            seconds_left = int((available_at - now).total_seconds())

            raise QrNotAvailableError(
                "Уход пока недоступен.",
                available_at=available_at,
                seconds_left=seconds_left,
            )

        record.checked_out_at = now
        record.checked_out_by = scanned_by
        record.save(update_fields=["checked_out_at", "checked_out_by"])
        sync_entry_attendance_status(entry, record)
        message = "Уход зафиксирован."

    else:
        raise ValueError("Неизвестное действие QR-кода.")

    token.is_used = True
    token.save(update_fields=["is_used"])

    # После успешной отметки гасим все остальные активные QR этого действия,
    # чтобы старые/параллельно созданные токены не могли быть использованы.
    _invalidate_active_tokens(entry, action=token.action)

    _create_attendance_log(
        entry=entry,
        action=token.action,
        scanned_by=scanned_by,
    )

    return _build_success_response(
        message=message,
        action=token.action,
        entry=entry,
        record=record,
    )


@transaction.atomic
def manual_mark_attendance(entry, marked_by, action):
    """
    Ручная отметка прихода/ухода администратором.

    Используется для таблицы назначенных участников на странице сканера:
    - check_in  — учесть приход вручную;
    - check_out — учесть уход вручную.
    """
    entry = _get_entry_with_related(
        entry_id=entry.id,
        entry_model=entry.__class__,
    )

    record = _get_locked_record(entry)

    now = timezone.now()

    if action == QrToken.ACTION_CHECK_IN:
        if record.checked_in_at:
            raise ValueError("Приход по этой смене уже зафиксирован.")

        record.checked_in_at = now
        record.checked_in_by = marked_by
        record.save(update_fields=["checked_in_at", "checked_in_by"])
        sync_entry_attendance_status(entry, record)
        message = "Приход учтён вручную."

    elif action == QrToken.ACTION_CHECK_OUT:
        if not record.checked_in_at:
            raise ValueError("Нельзя учесть уход до прихода.")

        if record.checked_out_at:
            raise ValueError("Уход по этой смене уже зафиксирован.")

        record.checked_out_at = now
        record.checked_out_by = marked_by
        record.save(update_fields=["checked_out_at", "checked_out_by"])
        sync_entry_attendance_status(entry, record)
        message = "Уход учтён вручную."

    else:
        raise ValueError("Неизвестное действие ручной отметки.")

    # После ручной отметки все активные QR этого действия нужно погасить,
    # иначе пользователь сможет отсканировать уже неактуальный QR.
    _invalidate_active_tokens(entry, action=action)

    _create_attendance_log(
        entry=entry,
        action=action,
        scanned_by=marked_by,
    )

    return _build_success_response(
        message=message,
        action=action,
        entry=entry,
        record=record,
    )
