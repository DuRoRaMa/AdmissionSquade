import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from .models import EmailVerificationCode


User = get_user_model()


DVFU_EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@(?:dvfu\.ru|students\.dvfu\.ru)$'


class EmailCodeError(Exception):
    pass


def normalize_email(email: str) -> str:
    return (email or '').lower().strip()


def validate_registration_email(email: str) -> str:
    email = normalize_email(email)

    if not re.match(DVFU_EMAIL_REGEX, email):
        raise EmailCodeError(
            'Разрешены только email адреса ДВФУ: name@dvfu.ru или name@students.dvfu.ru'
        )

    #if User.objects.filter(email=email).exists():
    #    raise EmailCodeError('Пользователь с таким email уже существует.')

    return email


def generate_code() -> str:
    return ''.join(secrets.choice('0123456789') for _ in range(6))


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
            f'Код уже отправлен. Повторная отправка доступна через {settings.EMAIL_CODE_RESEND_SECONDS} секунд.'
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
        subject='Код подтверждения регистрации',
        message=(
            f'Ваш код подтверждения регистрации: {code}\n\n'
            f'Код действует {settings.EMAIL_CODE_TTL_MINUTES} минут.\n'
            f'Если вы не регистрировались в системе, просто проигнорируйте это письмо.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )

    return verification_code


def verify_registration_code(email: str, code: str) -> EmailVerificationCode:
    email = normalize_email(email)
    code = (code or '').strip()

    verification_code = EmailVerificationCode.objects.filter(
        email=email,
        purpose=EmailVerificationCode.Purpose.REGISTRATION,
        used_at__isnull=True,
    ).order_by('-created_at').first()

    if not verification_code:
        raise EmailCodeError('Код подтверждения не найден. Запросите новый код.')

    if verification_code.is_expired:
        raise EmailCodeError('Срок действия кода истек. Запросите новый код.')

    if verification_code.attempts >= 5:
        raise EmailCodeError('Превышено количество попыток ввода кода. Запросите новый код.')

    verification_code.increase_attempts()

    if not constant_time_compare(verification_code.code, code):
        raise EmailCodeError('Неверный код подтверждения.')

    verification_code.mark_used()

    return verification_code