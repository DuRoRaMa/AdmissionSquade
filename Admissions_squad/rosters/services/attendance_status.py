from datetime import time

from django.utils import timezone

from rosters.models import ScheduleEntry, ScheduleRecord


STATUS_PLANNED = "planned"
STATUS_IN_PROGRESS = "in_progress"
STATUS_ATTENDED = "attended"
STATUS_ABSENT = "absent"
STATUS_CANCELLED = "cancelled"

FINAL_STATUSES = {
    STATUS_ATTENDED,
    STATUS_ABSENT,
    STATUS_CANCELLED,
}


def get_entry_end_datetime(entry):
    end_time = entry.ends_at or time(hour=23, minute=59, second=59)
    naive_value = timezone.datetime.combine(entry.date, end_time)

    return timezone.make_aware(
        naive_value,
        timezone.get_current_timezone(),
    )


def get_entry_record(entry):
    try:
        return entry.record
    except ScheduleRecord.DoesNotExist:
        return None


def get_entry_attendance_status(entry, record=None, now=None):
    """
    Единая логика статуса смены.

    Посетил:
        есть и приход, и уход.

    Не посетил:
        смена прошла, но нет двух отметок.

    На смене:
        есть приход, но нет ухода, и смена еще не прошла.

    Запланирована:
        смена еще не прошла и отметок нет.
    """
    now = now or timezone.now()
    record = record if record is not None else get_entry_record(entry)

    if entry.status == STATUS_CANCELLED:
        return STATUS_CANCELLED

    checked_in_at = record.checked_in_at if record else None
    checked_out_at = record.checked_out_at if record else None

    if checked_in_at and checked_out_at:
        return STATUS_ATTENDED

    if get_entry_end_datetime(entry) <= now:
        return STATUS_ABSENT

    if checked_in_at and not checked_out_at:
        return STATUS_IN_PROGRESS

    return STATUS_PLANNED


def sync_entry_attendance_status(entry, record=None, save=True):
    new_status = get_entry_attendance_status(entry, record)

    if entry.status != new_status:
        entry.status = new_status

        if save:
            entry.save(update_fields=["status"])

    return new_status


def close_past_schedule_entries(queryset=None):
    """
    Закрывает прошедшие смены.

    Нужна для случаев, когда день прошел, но отметку никто не трогал.
    """
    now = timezone.now()
    today = timezone.localdate()

    queryset = queryset or ScheduleEntry.objects.all()

    entries = (
        queryset
        .filter(date__lte=today)
        .exclude(status__in=FINAL_STATUSES)
        .select_related("record")
    )

    updated_count = 0

    for entry in entries:
        old_status = entry.status
        new_status = get_entry_attendance_status(entry, now=now)

        if old_status != new_status:
            entry.status = new_status
            entry.save(update_fields=["status"])
            updated_count += 1

    return updated_count
