from django.db import transaction
from rosters.models import AvailabilitySlot, AvailabilityFormShift, WorkBlock


@transaction.atomic
def submit_availability(form, membership, slots_data):

    allowed_shift_ids = set(
        AvailabilityFormShift.objects
        .filter(day__form=form, is_active=True)
        .values_list("id", flat=True)
    )

    allowed_work_block_ids = set(
        WorkBlock.objects
        .filter(squad=form.squad, is_active=True)
        .values_list("id", flat=True)
    )

    for item in slots_data:
        shift_id = item["shift_id"]

        if shift_id not in allowed_shift_ids:
            raise ValueError(f"Смена {shift_id} не принадлежит этой форме.")

        preferred_work_block_id = item.get("preferred_work_block")

        if preferred_work_block_id and not form.allow_work_block_choice:
            raise ValueError("В этой форме нельзя выбирать блок работы.")

        if preferred_work_block_id and preferred_work_block_id not in allowed_work_block_ids:
            raise ValueError("Выбранный блок работы недоступен для этого отряда.")

    AvailabilitySlot.objects.filter(
        shift__day__form=form,
        membership=membership
    ).delete()

    created = []

    for item in slots_data:
        preferred_work_block_id = item.get("preferred_work_block")

        if not item["is_available"]:
            preferred_work_block_id = None

        created.append(
            AvailabilitySlot(
                shift_id=item["shift_id"],
                membership=membership,
                is_available=item["is_available"],
                preferred_work_block_id=preferred_work_block_id,
                comment=item.get("comment", "")
            )
        )

    AvailabilitySlot.objects.bulk_create(created)
    return created