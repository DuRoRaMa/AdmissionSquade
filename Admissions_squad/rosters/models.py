from django.db import models
from django.conf import settings
from django.utils import timezone
from squads.models import Squad, SquadMembership
# Create your models here.


class WorkBlock(models.Model):
    squad = models.ForeignKey(
        Squad,
        on_delete=models.CASCADE,
        related_name='work_blocks'
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('squad', 'code')
        ordering = ['code']

    def __str__(self):
        return f'{self.squad.name}: {self.code}'


class AvailabilityForm(models.Model):
    STATUS_CODE = [
        ('draft', 'Черновик'),
        ('open', 'Открыта'),
        ('closed', 'Закрыта'),
    ]
    squad = models.ForeignKey(
        Squad,
        on_delete=models.CASCADE,
        related_name='availability_forms'
    )
    title = models.CharField(max_length=255)
    period_start = models.DateField()
    period_end = models.DateField()
    response_deadline = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CODE,
        default='draft'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class AvailabilityFormDay(models.Model):
    form = models.ForeignKey(
        AvailabilityForm,
        on_delete=models.CASCADE,
        related_name='days'
    )
    date = models.DateField()

    class Meta:
        unique_together = ('form', 'date')
        ordering = ['date']

    def __str__(self):
        return f'{self.form.title} - {self.date}'


class AvailabilityFormShift(models.Model):
    SHIFT_KIND_CHOICES = [
        ('primary', 'Основная смена'),
        ('extra', 'Дополнительная смена'),
    ]

    day = models.ForeignKey(
        AvailabilityFormDay,
        on_delete=models.CASCADE,
        related_name='shifts'
    )
    shift_kind = models.CharField(
        max_length=20,
        choices=SHIFT_KIND_CHOICES
    )
    title = models.CharField(
        max_length=100,
        blank=True
    )  # например, "Основная смена"
    starts_at = models.TimeField(
        null=True,
        blank=True
    )
    ends_at = models.TimeField(
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('day', 'shift_kind')
        ordering = ['starts_at', 'id']

    def __str__(self):
        return f'{self.day.date} - {self.get_shift_kind_display()}'


class AvailabilitySlot(models.Model):
    shift = models.ForeignKey(
        AvailabilityFormShift,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    membership = models.ForeignKey(
        SquadMembership,
        on_delete=models.CASCADE,
        related_name='availability_slots'
    )
    is_available = models.BooleanField(default=True)
    comment = models.CharField(max_length=255, blank=True)
    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('shift', 'membership')

    def __str__(self):
        return f'{self.membership} - {self.shift}'


class Schedule(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('published', 'Опубликован'),
        ('archived', 'Архив'),
    ]
    availability_form = models.ForeignKey(
        AvailabilityForm,
        on_delete=models.PROTECT,
        related_name='schedules',
        null=True,
        blank=True,
        verbose_name='Форма доступности',
    )
    squad = models.ForeignKey(
        Squad,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    title = models.CharField(max_length=255)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ScheduleNeed(models.Model):
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='needs'
    )
    date = models.DateField()
    work_block = models.ForeignKey(
        WorkBlock,
        on_delete=models.CASCADE,
        related_name='schedule_needs'
    )
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    required_people = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['date', 'starts_at']


class ScheduleEntry(models.Model):
    STATUS_CHOICES = [
        ("planned", "Запланирована"),
        ("in_progress", "На смене"),
        ("attended", "Посетил"),
        ("absent", "Не посетил"),
        ("cancelled", "Отменена"),

        # legacy-статус
        ("completed", "Завершена"),
    ]
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='entries'
    )
    need = models.ForeignKey(
        ScheduleNeed,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    membership = models.ForeignKey(
        SquadMembership,
        on_delete=models.CASCADE,
        related_name='schedule_entries'
    )
    work_block = models.ForeignKey(WorkBlock, on_delete=models.PROTECT)
    date = models.DateField()
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planned'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'starts_at']


class ScheduleChangeRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('approved', 'Одобрена'),
        ('rejected', 'Отклонена'),
    ]

    REQUEST_TYPE_CHOICES = [
        ('cancel', 'Не могу выйти'),
        ('swap', 'Прошу замену'),
        ('time_change', 'Изменение времени'),
    ]

    entry = models.ForeignKey(
        ScheduleEntry,
        on_delete=models.CASCADE,
        related_name='change_requests'
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='schedule_change_requests'
    )
    request_type = models.CharField(
        max_length=20,
        choices=REQUEST_TYPE_CHOICES
    )
    reason = models.TextField()
    target_membership = models.ForeignKey(
        SquadMembership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incoming_change_requests'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_schedule_change_requests'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ScheduleRecord(models.Model):
    entry = models.OneToOneField(
        ScheduleEntry,
        on_delete=models.CASCADE,
        related_name='record'
    )
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkins_made'
    )
    checked_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkouts_made'
    )


class QrToken(models.Model):
    ACTION_CHECK_IN = "check_in"
    ACTION_CHECK_OUT = "check_out"

    ACTION_CHOICES = [
        (ACTION_CHECK_IN, "Приход"),
        (ACTION_CHECK_OUT, "Уход"),
    ]
    entry = models.ForeignKey(
        ScheduleEntry,
        on_delete=models.CASCADE,
        related_name='qr_tokens'
    )
    token = models.CharField(max_length=128, unique=True)
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        default=ACTION_CHECK_IN,
    )
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["entry", "action", "is_used"]),
        ]

    def is_expired(self):
        return timezone.now() >= self.expires_at


class AttendanceActionLog(models.Model):
    ACTION_CHECK_IN = "check_in"
    ACTION_CHECK_OUT = "check_out"

    ACTION_CHOICES = [
        (ACTION_CHECK_IN, "Приход"),
        (ACTION_CHECK_OUT, "Уход"),
    ]

    entry = models.ForeignKey(
        ScheduleEntry,
        on_delete=models.CASCADE,
        related_name="attendance_logs",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_scans",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["entry", "action"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.entry_id} - {self.created_at}"
