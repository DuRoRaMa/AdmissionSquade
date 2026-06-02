from django.db import transaction
from django.db.models import Max

from rosters.models import AvailabilitySlot, ScheduleEntry


MIN_REST_DAYS_PRIORITY = 3

ASSIGNMENT_STATUSES_FOR_HISTORY = (
    "planned",
    "in_progress",
    "attended",
    "completed",
)


def intervals_intersect(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def get_member_name(membership):
    user = membership.user

    if not user:
        return ""

    full_name = f"{user.last_name} {user.first_name} {user.middle_name}".strip()

    return full_name or user.email or ""


def get_last_assignment_dates(schedule):
    """
    Возвращает последнюю дату назначения участника до начала текущего графика.

    Используется для приоритета участников, которые давно не выходили.
    При дальнейшей генерации словарь обновляется уже созданными назначениями.
    """
    rows = (
        ScheduleEntry.objects
        .filter(
            schedule__squad=schedule.squad,
            membership__squad=schedule.squad,
            date__lt=schedule.period_start,
            status__in=ASSIGNMENT_STATUSES_FOR_HISTORY,
        )
        .values("membership_id")
        .annotate(last_date=Max("date"))
    )

    return {
        row["membership_id"]: row["last_date"]
        for row in rows
    }


def get_days_without_assignment(last_assignment_date, current_date):
    if not last_assignment_date:
        return None

    return (current_date - last_assignment_date).days


def get_work_block_priority(slot, need):
    """
    Чем меньше число, тем выше приоритет.

    0 — участник выбрал именно этот блок;
    1 — участник доступен, но блок не выбрал;
    2 — участник выбрал другой блок.
    """
    preferred_work_block_id = slot.preferred_work_block_id

    if preferred_work_block_id == need.work_block_id:
        return 0

    if preferred_work_block_id is None:
        return 1

    return 2


def get_rest_priority(slot, need, last_assignment_dates):
    """
    Чем меньше число, тем выше приоритет.

    Участники, которые не назначались 3 дня и более,
    получают преимущество внутри своей группы по блоку работы.
    """
    last_assignment_date = last_assignment_dates.get(slot.membership_id)
    days_without_assignment = get_days_without_assignment(
        last_assignment_date,
        need.date,
    )

    if days_without_assignment is None:
        return 0

    if days_without_assignment >= MIN_REST_DAYS_PRIORITY:
        return 0

    return 1


def get_rest_sort_value(slot, need, last_assignment_dates):
    """
    Дополнительная сортировка внутри rest_priority.

    Чем больше дней участник не выходил, тем выше он будет в списке.
    Для участников без истории назначений ставим большое значение.
    """
    last_assignment_date = last_assignment_dates.get(slot.membership_id)
    days_without_assignment = get_days_without_assignment(
        last_assignment_date,
        need.date,
    )

    if days_without_assignment is None:
        return -9999

    return -days_without_assignment


def get_candidate_sort_key(slot, need, last_assignment_dates, generated_counts):
    membership = slot.membership

    return (
        get_work_block_priority(slot, need),
        get_rest_priority(slot, need, last_assignment_dates),
        get_rest_sort_value(slot, need, last_assignment_dates),
        generated_counts.get(membership.id, 0),
        get_member_name(membership).lower(),
        membership.id,
    )


def get_candidates_for_need(schedule, need):
    """
    Получает всех участников, которые указали доступность
    на дату и смену текущей потребности.
    """
    return (
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
        .select_related(
            "membership",
            "membership__user",
            "shift",
            "shift__day",
            "preferred_work_block",
        )
    )


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
        .order_by("date", "starts_at", "work_block__name", "id")
    )

    last_assignment_dates = get_last_assignment_dates(schedule)
    generated_counts = {}
    assigned_memberships_by_date = {}

    for need in needs:
        assigned_today = assigned_memberships_by_date.setdefault(
            need.date,
            set(),
        )

        candidates = list(get_candidates_for_need(schedule, need))

        candidates.sort(
            key=lambda slot: get_candidate_sort_key(
                slot,
                need,
                last_assignment_dates,
                generated_counts,
            )
        )

        created_count = 0

        for slot in candidates:
            membership = slot.membership

            # Один участник не должен закрывать две потребности в один день.
            if membership.id in assigned_today:
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

            assigned_today.add(membership.id)
            last_assignment_dates[membership.id] = need.date
            generated_counts[membership.id] = generated_counts.get(membership.id, 0) + 1

            created_count += 1

            if created_count >= need.required_people:
                break

    return schedule
