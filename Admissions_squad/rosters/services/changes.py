from django.db import transaction
from django.utils import timezone


@transaction.atomic
def approve_change_request(change_request, reviewer):
    if change_request.status != "pending":
        raise ValueError("Заявка уже обработана.")

    entry = change_request.entry

    if change_request.request_type == "cancel":
        entry.status = "cancelled"
        entry.save(update_fields=["status"])

    elif change_request.request_type == "swap":
        if not change_request.target_membership:
            raise ValueError("Для заявки на замену нужно указать участника.")

        target_membership = change_request.target_membership

        if target_membership.squad_id != entry.membership.squad_id:
            raise ValueError("Нельзя передать смену участнику из другого отряда.")

        if not target_membership.is_active:
            raise ValueError("Нельзя передать смену неактивному участнику.")

        entry.membership = target_membership
        entry.status = "planned"
        entry.save(update_fields=["membership", "status"])

    elif change_request.request_type == "time_change":
        raise ValueError("Изменение времени пока не поддерживается.")

    else:
        raise ValueError("Неизвестный тип заявки.")

    change_request.status = "approved"
    change_request.reviewed_by = reviewer
    change_request.reviewed_at = timezone.now()
    change_request.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
        ]
    )

    return change_request


@transaction.atomic
def reject_change_request(change_request, reviewer, comment=""):
    if change_request.status != "pending":
        raise ValueError("Заявка уже обработана.")

    change_request.status = "rejected"
    change_request.reviewed_by = reviewer
    change_request.reviewed_at = timezone.now()
    change_request.review_comment = comment or ""
    change_request.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_comment",
        ]
    )

    return change_request
