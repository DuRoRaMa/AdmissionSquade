from django.utils import timezone

from rosters.models import AvailabilityForm


def close_expired_availability_forms(now=None):
    """
    Закрывает все открытые формы доступности,
    у которых истек срок отправки ответов.
    """
    now = now or timezone.now()

    return (
        AvailabilityForm.objects
        .filter(
            status="open",
            response_deadline__isnull=False,
            response_deadline__lte=now,
        )
        .update(status="closed")
    )


def close_form_if_deadline_expired(form, now=None):
    """
    Закрывает конкретную форму, если дедлайн истек.
    Возвращает True, если форма была закрыта.
    """
    now = now or timezone.now()

    if (
        form.status == "open"
        and form.response_deadline
        and form.response_deadline <= now
    ):
        form.status = "closed"
        form.save(update_fields=["status"])
        return True

    return False


def is_form_deadline_expired(form, now=None):
    now = now or timezone.now()

    return bool(
        form.response_deadline
        and form.response_deadline <= now
    )