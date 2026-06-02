import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from squads.models import SquadMembership

from .email_service import send_pending_notification_emails
from .models import EmailVerificationCode, Notification


User = get_user_model()

DVFU_EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@(?:dvfu\.ru|students\.dvfu\.ru)$"


class EmailCodeError(Exception):
    pass


def normalize_email(email: str) -> str:
    return (email or "").lower().strip()


def validate_registration_email(email: str) -> str:
    email = normalize_email(email)

    if not re.match(DVFU_EMAIL_REGEX, email):
        raise EmailCodeError(
            "Разрешены только email адреса ДВФУ: name@dvfu.ru или name@students.dvfu.ru"
        )

    return email


def generate_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(6))


def send_registration_code(email: str) -> EmailVerificationCode:
    email = validate_registration_email(email)

    now = timezone.now()
    resend_delta = timedelta(seconds=settings.EMAIL_CODE_RESEND_SECONDS)

    recent_code_exists = EmailVerificationCode.objects.filter(
        email=email,
        purpose=EmailVerificationCode.Purpose.REGISTRATION,
        used_at__isnull=True,
        created_at__gte=now - resend_delta,
    ).exists()

    if recent_code_exists:
        raise EmailCodeError(
            f"Код уже отправлен. Повторная отправка доступна через "
            f"{settings.EMAIL_CODE_RESEND_SECONDS} секунд."
        )

    EmailVerificationCode.objects.filter(
        email=email,
        purpose=EmailVerificationCode.Purpose.REGISTRATION,
        used_at__isnull=True,
    ).update(used_at=now)

    code = generate_code()

    verification_code = EmailVerificationCode.objects.create(
        email=email,
        code=code,
        purpose=EmailVerificationCode.Purpose.REGISTRATION,
        expires_at=now + timedelta(minutes=settings.EMAIL_CODE_TTL_MINUTES),
    )

    send_mail(
        subject="Код подтверждения регистрации",
        message=(
            f"Ваш код подтверждения регистрации: {code}\n\n"
            f"Код действует {settings.EMAIL_CODE_TTL_MINUTES} минут.\n"
            f"Если вы не регистрировались в системе, просто проигнорируйте это письмо."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )

    return verification_code


def verify_registration_code(email: str, code: str) -> EmailVerificationCode:
    email = normalize_email(email)
    code = (code or "").strip()

    verification_code = (
        EmailVerificationCode.objects.filter(
            email=email,
            purpose=EmailVerificationCode.Purpose.REGISTRATION,
            used_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )

    if not verification_code:
        raise EmailCodeError("Код подтверждения не найден. Запросите новый код.")

    if verification_code.is_expired:
        raise EmailCodeError("Срок действия кода истек. Запросите новый код.")

    if verification_code.attempts >= 5:
        raise EmailCodeError("Превышено количество попыток ввода кода. Запросите новый код.")

    verification_code.increase_attempts()

    if not constant_time_compare(verification_code.code, code):
        raise EmailCodeError("Неверный код подтверждения.")

    verification_code.mark_used()

    return verification_code


EMAIL_EVENTS = {
    Notification.EventType.AVAILABILITY_FORM_OPENED,
    Notification.EventType.SCHEDULE_PUBLISHED,
    Notification.EventType.SCHEDULE_CHANGED,
    Notification.EventType.CHANGE_REQUEST_CREATED,
    Notification.EventType.CHANGE_REQUEST_APPROVED,
    Notification.EventType.CHANGE_REQUEST_REJECTED,
}


def should_send_email(event_type):
    return event_type in EMAIL_EVENTS


def build_email_body(title, message, object_url=""):
    lines = [
        title,
        "",
        message or "",
    ]

    if object_url:
        lines.extend(
            [
                "",
                "Перейдите в систему, чтобы посмотреть подробности.",
                object_url,
            ]
        )

    return "\n".join(lines).strip()


def schedule_email_delivery(notification_ids):
    if not notification_ids:
        return

    transaction.on_commit(
        lambda: send_pending_notification_emails(notification_ids)
    )


def create_notification(
    recipient,
    title,
    message="",
    event_type=Notification.EventType.SYSTEM,
    object_url="",
    metadata=None,
    send_email=None,
    email_subject="",
    email_body="",
):
    if not recipient:
        return None

    email_required = should_send_email(event_type) if send_email is None else bool(send_email)

    notification = Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message or "",
        event_type=event_type,
        object_url=object_url or "",
        metadata=metadata or {},
        email_required=email_required,
        email_to=recipient.email if email_required else "",
        email_subject=email_subject or title if email_required else "",
        email_body=(
            email_body
            or build_email_body(title, message, object_url)
            if email_required
            else ""
        ),
        email_status=(
            Notification.EmailStatus.PENDING
            if email_required
            else Notification.EmailStatus.NOT_REQUIRED
        ),
    )

    if notification.email_required:
        schedule_email_delivery([notification.id])

    return notification


def create_notifications(
    recipients,
    title,
    message="",
    event_type=Notification.EventType.SYSTEM,
    object_url="",
    metadata=None,
    send_email=None,
    email_subject="",
    email_body="",
):
    unique_recipients = []
    seen_user_ids = set()

    for recipient in recipients:
        if not recipient or not recipient.id or recipient.id in seen_user_ids:
            continue

        seen_user_ids.add(recipient.id)
        unique_recipients.append(recipient)

    email_required = should_send_email(event_type) if send_email is None else bool(send_email)

    notifications = [
        Notification(
            recipient=recipient,
            title=title,
            message=message or "",
            event_type=event_type,
            object_url=object_url or "",
            metadata=metadata or {},
            email_required=email_required,
            email_to=recipient.email if email_required else "",
            email_subject=email_subject or title if email_required else "",
            email_body=(
                email_body
                or build_email_body(title, message, object_url)
                if email_required
                else ""
            ),
            email_status=(
                Notification.EmailStatus.PENDING
                if email_required
                else Notification.EmailStatus.NOT_REQUIRED
            ),
        )
        for recipient in unique_recipients
    ]

    created_notifications = Notification.objects.bulk_create(notifications)

    email_notification_ids = [
        notification.id
        for notification in created_notifications
        if notification.email_required
    ]

    schedule_email_delivery(email_notification_ids)

    return created_notifications


def get_squad_active_users(squad):
    memberships = (
        SquadMembership.objects
        .filter(squad=squad, is_active=True)
        .select_related("user")
    )

    return [
        membership.user
        for membership in memberships
        if membership.user and membership.user.is_active
    ]


def get_squad_managers(squad):
    from rosters.permissions import can_manage_roster

    memberships = (
        SquadMembership.objects
        .filter(squad=squad, is_active=True)
        .select_related("user", "role")
    )

    managers = []

    for membership in memberships:
        user = membership.user

        if user and user.is_active and can_manage_roster(user, squad):
            managers.append(user)

    return managers


def get_user_name(user):
    if not user:
        return ""

    return user.get_full_name() or user.username or user.email


def notify_availability_form_opened(form):
    recipients = get_squad_active_users(form.squad)

    return create_notifications(
        recipients=recipients,
        title="Открыта форма доступности",
        message=(
            f"Открыта форма «{form.title}» на период "
            f"{form.period_start} — {form.period_end}. "
            f"Заполните доступность до {form.response_deadline}."
        ),
        event_type=Notification.EventType.AVAILABILITY_FORM_OPENED,
        object_url="/availability",
        metadata={
            "form_id": form.id,
            "squad_id": form.squad_id,
        },
        send_email=True,
    )


def notify_schedule_published(schedule):
    user_ids = (
        schedule.entries
        .select_related("membership__user")
        .values_list("membership__user_id", flat=True)
        .distinct()
    )

    recipients = User.objects.filter(id__in=user_ids, is_active=True)

    return create_notifications(
        recipients=recipients,
        title="Опубликован график",
        message=(
            f"Опубликован график «{schedule.title}» на период "
            f"{schedule.period_start} — {schedule.period_end}."
        ),
        event_type=Notification.EventType.SCHEDULE_PUBLISHED,
        object_url="/schedule",
        metadata={
            "schedule_id": schedule.id,
            "squad_id": schedule.squad_id,
        },
        send_email=True,
    )


def notify_change_request_created(change_request):
    entry = change_request.entry
    schedule = entry.schedule

    recipients = get_squad_managers(schedule.squad)
    requester_name = get_user_name(change_request.requested_by)

    return create_notifications(
        recipients=recipients,
        title="Новая заявка на изменение графика",
        message=f"{requester_name} отправил(а) заявку по смене {entry.date}.",
        event_type=Notification.EventType.CHANGE_REQUEST_CREATED,
        object_url="/dashboard/change-requests",
        metadata={
            "change_request_id": change_request.id,
            "entry_id": entry.id,
            "schedule_id": schedule.id,
            "squad_id": schedule.squad_id,
            "request_type": change_request.request_type,
        },
        send_email=True,
    )


def notify_change_request_approved(change_request):
    recipients = [change_request.requested_by]

    if change_request.request_type == "swap" and change_request.target_membership:
        recipients.append(change_request.target_membership.user)

    return create_notifications(
        recipients=recipients,
        title="Заявка одобрена",
        message="Командир одобрил заявку на изменение графика.",
        event_type=Notification.EventType.CHANGE_REQUEST_APPROVED,
        object_url="/schedule/requests",
        metadata={
            "change_request_id": change_request.id,
            "entry_id": change_request.entry_id,
            "request_type": change_request.request_type,
        },
        send_email=True,
    )


def notify_change_request_rejected(change_request):
    return create_notification(
        recipient=change_request.requested_by,
        title="Заявка отклонена",
        message=(
            change_request.review_comment
            or "Командир отклонил заявку на изменение графика."
        ),
        event_type=Notification.EventType.CHANGE_REQUEST_REJECTED,
        object_url="/schedule/requests",
        metadata={
            "change_request_id": change_request.id,
            "entry_id": change_request.entry_id,
            "request_type": change_request.request_type,
        },
        send_email=True,
    )
