from django.db import models

# Create your models here.
from django.db import models
from django.utils import timezone


class EmailVerificationCode(models.Model):
    class Purpose(models.TextChoices):
        REGISTRATION = 'registration', 'Регистрация'

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
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'purpose', 'used_at']),
        ]

    def __str__(self):
        return f'{self.email} — {self.purpose}'

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=['used_at'])

    def increase_attempts(self):
        self.attempts += 1
        self.save(update_fields=['attempts'])