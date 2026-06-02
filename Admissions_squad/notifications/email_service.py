from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Notification


def send_notification_email(notification):
    if not notification.email_required:
        return notification

    if notification.email_status == Notification.EmailStatus.SENT:
        return notification

    if not notification.email_to:
        notification.email_status = Notification.EmailStatus.FAILED
        notification.email_error = "Не указан email получателя."
        notification.save(update_fields=["email_status", "email_error"])
        return notification

    try:
        send_mail(
            subject=notification.email_subject or notification.title,
            message=notification.email_body or notification.message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.email_to],
            fail_silently=False,
        )
    except Exception as error:
        notification.email_status = Notification.EmailStatus.FAILED
        notification.email_error = str(error)
        notification.save(update_fields=["email_status", "email_error"])
        return notification

    notification.email_status = Notification.EmailStatus.SENT
    notification.email_sent_at = timezone.now()
    notification.email_error = ""
    notification.save(
        update_fields=[
            "email_status",
            "email_sent_at",
            "email_error",
        ]
    )

    return notification


def send_pending_notification_emails(notification_ids):
    notifications = Notification.objects.filter(
        id__in=notification_ids,
        email_required=True,
        email_status=Notification.EmailStatus.PENDING,
    ).select_related("recipient")

    for notification in notifications:
        send_notification_email(notification)
