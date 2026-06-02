from django.conf import settings
from django.db import models
from django.utils import timezone


class EmailVerificationCode(models.Model):
    class Purpose(models.TextChoices):
        REGISTRATION = "registration", "Регистрация"

    email = models.EmailField(db_index=True)
    code = models.CharField(max_length=6)

    purpose = models.CharField(
        max_length=32,
        choices=Purpose.choices,
        default=Purpose.REGISTRATION,
        db_index=True,
    )

    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "purpose", "used_at"]),
        ]

    def __str__(self):
        return f"{self.email} — {self.purpose}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def increase_attempts(self):
        self.attempts += 1
        self.save(update_fields=["attempts"])


class Notification(models.Model):
    class EventType(models.TextChoices):
        SYSTEM = "system", "Системное уведомление"
        USER_REGISTERED = "user_registered", "Новый пользователь"
        AVAILABILITY_FORM_OPENED = "availability_form_opened", "Открыта форма доступности"
        SCHEDULE_PUBLISHED = "schedule_published", "График опубликован"
        SCHEDULE_CHANGED = "schedule_changed", "График изменён"
        CHANGE_REQUEST_CREATED = "change_request_created", "Новая заявка"
        CHANGE_REQUEST_APPROVED = "change_request_approved", "Заявка одобрена"
        CHANGE_REQUEST_REJECTED = "change_request_rejected", "Заявка отклонена"

    class EmailStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", "Email не требуется"
        PENDING = "pending", "Ожидает отправки"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка отправки"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Получатель",
    )

    event_type = models.CharField(
        max_length=64,
        choices=EventType.choices,
        default=EventType.SYSTEM,
        verbose_name="Тип события",
    )

    title = models.CharField(
        max_length=255,
        verbose_name="Заголовок",
    )

    message = models.TextField(
        blank=True,
        verbose_name="Текст уведомления",
    )

    object_url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Ссылка в интерфейсе",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Дополнительные данные",
    )

    is_read = models.BooleanField(
        default=False,
        verbose_name="Прочитано",
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата прочтения",
    )

    email_required = models.BooleanField(
        default=False,
        verbose_name="Требуется email",
    )

    email_to = models.EmailField(
        blank=True,
        verbose_name="Email получателя",
    )

    email_subject = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Тема письма",
    )

    email_body = models.TextField(
        blank=True,
        verbose_name="Текст письма",
    )

    email_status = models.CharField(
        max_length=32,
        choices=EmailStatus.choices,
        default=EmailStatus.NOT_REQUIRED,
        verbose_name="Статус email",
    )

    email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата отправки email",
    )

    email_error = models.TextField(
        blank=True,
        verbose_name="Ошибка email",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(fields=["event_type"]),
            models.Index(fields=["email_status"]),
        ]
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"

    def __str__(self):
        return f"{self.title} → {self.recipient}"

    def mark_as_read(self):
        if self.is_read:
            return

        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at"])
