from __future__ import annotations

import pytest

from rosters.models import ScheduleEntry
from rosters.services.generator import generate_schedule
from .conftest import DAY_1, PRIMARY_START, authenticate, create_need, create_slot


pytestmark = pytest.mark.django_db


def test_generate_schedule_fills_required_people(
    schedule,
    closed_availability_form,
    work_block,
    member_one,
    member_two,
    member_three,
):
    create_need(
        schedule=schedule,
        work_block=work_block,
        day_date=DAY_1,
        shift_kind="primary",
        required_people=2,
    )
    for membership in (member_one, member_two, member_three):
        create_slot(
            form=closed_availability_form,
            membership=membership,
            day_date=DAY_1,
            shift_kind="primary",
            available=True,
        )

    generate_schedule(schedule)

    entries = ScheduleEntry.objects.filter(schedule=schedule, date=DAY_1)
    assert entries.count() == 2
    assert set(entries.values_list("membership_id", flat=True)).issubset(
        {member_one.id, member_two.id, member_three.id}
    )


def test_generate_schedule_does_not_assign_unavailable_members(
    schedule,
    closed_availability_form,
    work_block,
    member_one,
    member_two,
):
    create_need(
        schedule=schedule,
        work_block=work_block,
        day_date=DAY_1,
        shift_kind="primary",
        required_people=1,
    )
    create_slot(
        form=closed_availability_form,
        membership=member_one,
        day_date=DAY_1,
        shift_kind="primary",
        available=False,
    )
    create_slot(
        form=closed_availability_form,
        membership=member_two,
        day_date=DAY_1,
        shift_kind="primary",
        available=True,
    )

    generate_schedule(schedule)

    entry = ScheduleEntry.objects.get(schedule=schedule, date=DAY_1)
    assert entry.membership == member_two


def test_generate_schedule_respects_availability_shift_time(
    schedule,
    closed_availability_form,
    work_block,
    member_one,
    member_two,
):
    """
    Ключевая проверка для текущей проблемы генерации.

    Участник, который доступен только на дополнительную смену 18:00-21:00,
    не должен попадать на основную смену 09:00-18:00.
    """
    create_need(
        schedule=schedule,
        work_block=work_block,
        day_date=DAY_1,
        shift_kind="primary",
        required_people=1,
    )
    create_slot(
        form=closed_availability_form,
        membership=member_one,
        day_date=DAY_1,
        shift_kind="extra",
        available=True,
    )
    create_slot(
        form=closed_availability_form,
        membership=member_two,
        day_date=DAY_1,
        shift_kind="primary",
        available=True,
    )

    generate_schedule(schedule)

    entry = ScheduleEntry.objects.get(schedule=schedule, date=DAY_1, starts_at=PRIMARY_START)
    assert entry.membership == member_two


def test_generate_schedule_does_not_assign_same_member_twice_in_one_day(
    schedule,
    closed_availability_form,
    work_block,
    second_work_block,
    member_one,
    member_two,
):
    create_need(
        schedule=schedule,
        work_block=work_block,
        day_date=DAY_1,
        shift_kind="primary",
        required_people=1,
    )
    create_need(
        schedule=schedule,
        work_block=second_work_block,
        day_date=DAY_1,
        shift_kind="extra",
        required_people=1,
    )
    create_slot(
        form=closed_availability_form,
        membership=member_one,
        day_date=DAY_1,
        shift_kind="primary",
        available=True,
    )
    create_slot(
        form=closed_availability_form,
        membership=member_one,
        day_date=DAY_1,
        shift_kind="extra",
        available=True,
    )
    create_slot(
        form=closed_availability_form,
        membership=member_two,
        day_date=DAY_1,
        shift_kind="extra",
        available=True,
    )

    generate_schedule(schedule)

    entries = ScheduleEntry.objects.filter(schedule=schedule, date=DAY_1)
    assert entries.count() == 2
    assert entries.values("membership_id").distinct().count() == 2


def test_generate_endpoint_is_idempotent_for_draft_schedule(
    api_client,
    staff_user,
    schedule,
    closed_availability_form,
    work_block,
    member_one,
):
    authenticate(api_client, staff_user)
    create_need(schedule=schedule, work_block=work_block, day_date=DAY_1, shift_kind="primary")
    create_slot(
        form=closed_availability_form,
        membership=member_one,
        day_date=DAY_1,
        shift_kind="primary",
        available=True,
    )

    first_response = api_client.post(f"/api/v1/rosters/schedules/{schedule.id}/generate/")
    second_response = api_client.post(f"/api/v1/rosters/schedules/{schedule.id}/generate/")

    assert first_response.status_code == 200, first_response.data
    assert second_response.status_code == 200, second_response.data
    assert ScheduleEntry.objects.filter(schedule=schedule).count() == 1
