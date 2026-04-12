import secrets
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from rosters.models import QrToken, ScheduleRecord


def create_qr_token(entry):
    return QrToken.objects.create(
        entry=entry,
        token=secrets.token_urlsafe(32),
        expires_at=timezone.now() + timedelta(minutes=3),
        is_used=False
    )


@transaction.atomic
def scan_qr(token_value, scanned_by):
    token = (
        QrToken.objects
        .select_related('entry')
        .filter(token=token_value)
        .first()
    )

    if not token:
        raise ValueError('QR-токен не найден.')

    if token.is_expired():
        raise ValueError('Срок действия QR-кода истёк.')

    entry = token.entry
    record, _ = ScheduleRecord.objects.get_or_create(entry=entry)

    if not record.checked_in_at:
        record.checked_in_at = timezone.now()
        record.checked_in_by = scanned_by
        record.save(update_fields=['checked_in_at', 'checked_in_by'])
        token.is_used = True
        token.save(update_fields=['is_used'])
        return {'message': 'Приход зафиксирован'}

    if not record.checked_out_at:
        record.checked_out_at = timezone.now()
        record.checked_out_by = scanned_by
        record.save(update_fields=['checked_out_at', 'checked_out_by'])
        token.is_used = True
        token.save(update_fields=['is_used'])
        return {'message': 'Уход зафиксирован'}

    raise ValueError('Смена уже полностью отмечена.')