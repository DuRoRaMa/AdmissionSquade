from django.db import transaction

from rosters.models import ScheduleEntry, AvailabilitySlot


def intervals_intersect(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


@transaction.atomic
def generate_schedule(schedule):
    if not schedule.availability_form_id:
        raise ValueError("Для графика не выбрана форма доступности.")

    if schedule.availability_form.status != "closed":
        raise ValueError("График можно формировать только по закрытой форме доступности.")

    schedule.entries.all().delete()

    needs = (
        schedule.needs
        .select_related("work_block")
        .all()
        .order_by("date", "starts_at")
    )

    for need in needs:
        candidates = (
            AvailabilitySlot.objects
            .filter(
                shift__day__form=schedule.availability_form,
                shift__day__date=need.date,
                shift__starts_at__lte=need.starts_at,
                shift__ends_at__gte=need.ends_at,
                is_available=True,
                membership__is_active=True,
                membership__squad=schedule.squad,
            )
            .select_related("membership", "shift")
            .order_by("membership_id")
        )

        count = 0

        for slot in candidates:
            membership = slot.membership

            already_busy = ScheduleEntry.objects.filter(
                schedule=schedule,
                membership=membership,
                date=need.date,
                status="planned",
                starts_at__lt=need.ends_at,
                ends_at__gt=need.starts_at,
            ).exists()

            if already_busy:
                continue

            ScheduleEntry.objects.create(
                schedule=schedule,
                need=need,
                membership=membership,
                work_block=need.work_block,
                date=need.date,
                starts_at=need.starts_at,
                ends_at=need.ends_at,
                status="planned",
            )

            count += 1

            if count >= need.required_people:
                break

    return schedule