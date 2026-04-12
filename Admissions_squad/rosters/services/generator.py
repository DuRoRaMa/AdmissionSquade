from django.db import transaction
from rosters.models import ScheduleEntry, AvailabilitySlot


@transaction.atomic
def generate_schedule(schedule):
    schedule.entries.all().delete()

    needs = schedule.needs.select_related('work_block').all().order_by('date', 'starts_at')

    for need in needs:
        candidates = (
            AvailabilitySlot.objects
            .filter(
                shift__day__form__squad=schedule.squad,
                shift__day__date=need.date,
                is_available=True,
                membership__is_active=True,
            )
            .select_related('membership', 'shift')
            .order_by('membership_id')
        )

        assigned_memberships = set()
        count = 0

        for slot in candidates:
            membership = slot.membership

            if membership.id in assigned_memberships:
                continue

            already_busy = ScheduleEntry.objects.filter(
                schedule=schedule,
                membership=membership,
                date=need.date,
                status='planned'
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
                status='planned'
            )
            assigned_memberships.add(membership.id)
            count += 1

            if count >= need.required_people:
                break

    return schedule