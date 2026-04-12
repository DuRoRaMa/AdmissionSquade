from django.db import transaction
from rosters.models import AvailabilitySlot, AvailabilityFormShift


@transaction.atomic
def submit_availability(form, membership, slots_data):
    shift_ids = [item['shift_id'] for item in slots_data]

    allowed_shift_ids = set(
        AvailabilityFormShift.objects.filter(day__form=form, is_active=True).values_list('id', flat=True)
    )

    for shift_id in shift_ids:
        if shift_id not in allowed_shift_ids:
            raise ValueError(f'Смена {shift_id} не принадлежит этой форме.')

    AvailabilitySlot.objects.filter(
        shift__day__form=form,
        membership=membership
    ).delete()

    created = []
    for item in slots_data:
        created.append(
            AvailabilitySlot(
                shift_id=item['shift_id'],
                membership=membership,
                is_available=item['is_available'],
                comment=item.get('comment', '')
            )
        )

    AvailabilitySlot.objects.bulk_create(created)
    return created