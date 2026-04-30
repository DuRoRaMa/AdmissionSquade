from __future__ import annotations

import pytest

from rosters.models import Schedule, ScheduleEntry, ScheduleNeed
from .conftest import (
    DAY_1,
    DAY_2,
    EXTRA_END,
    EXTRA_START,
    PRIMARY_END,
    PRIMARY_START,
    authenticate,
    create_need,
    create_slot,
    get_shift,
)


pytestmark = pytest.mark.django_db


def test_admin_can_create_schedule_from_closed_availability_form(
    api_client,
    staff_user,
    squad,
    closed_availability_form,
    work_block,
):
    authenticate(api_client, staff_user)

    response = api_client.post(
        "/api/v1/rosters/schedules/",
        {
            "squad": squad.id,
            "availability_form": closed_availability_form.id,
            "title": "График апрель",
            "needs": [
                {
                    "date": "2026-04-13",
                    "work_block": work_block.id,
                    "starts_at": "09:00:00",
                    "ends_at": "18:00:00",
                    "required_people": 2,
                }
            ],
        },
        format="json",
    )

    assert response.status_code == 201, response.data
    schedule = Schedule.objects.get(pk=response.data["id"])
    assert schedule.period_start == closed_availability_form.period_start
    assert schedule.period_end == closed_availability_form.period_end
    assert schedule.needs.count() == 1
    assert response.data["has_entries"] is False
    assert response.data["entries_count"] == 0


def test_schedule_create_requires_closed_availability_form(
    api_client,
    staff_user,
    squad,
    open_availability_form,
    work_block,
):
    authenticate(api_client, staff_user)

    response = api_client.post(
        "/api/v1/rosters/schedules/",
        {
            "squad": squad.id,
            "availability_form": open_availability_form.id,
            "title": "График по открытой форме",
            "needs": [
                {
                    "date": "2026-04-13",
                    "work_block": work_block.id,
                    "starts_at": "09:00:00",
                    "ends_at": "18:00:00",
                    "required_people": 1,
                }
            ],
        },
        format="json",
    )

    assert response.status_code == 400


def test_generate_publish_export_and_delete_schedule(
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

    generate_response = api_client.post(f"/api/v1/rosters/schedules/{schedule.id}/generate/")
    assert generate_response.status_code == 200, generate_response.data
    assert generate_response.data["has_entries"] is True
    assert generate_response.data["entries_count"] == 1
    assert ScheduleEntry.objects.filter(schedule=schedule).count() == 1

    export_response = api_client.get(f"/api/v1/rosters/schedules/{schedule.id}/export/")
    assert export_response.status_code == 200
    assert export_response.content.startswith(b"PK")

    publish_response = api_client.post(f"/api/v1/rosters/schedules/{schedule.id}/publish/")
    assert publish_response.status_code == 200, publish_response.data
    schedule.refresh_from_db()
    assert schedule.status == "published"

    second_generate_response = api_client.post(f"/api/v1/rosters/schedules/{schedule.id}/generate/")
    assert second_generate_response.status_code == 400

    delete_response = api_client.delete(f"/api/v1/rosters/schedules/{schedule.id}/")
    assert delete_response.status_code in (200, 202, 204), delete_response.content
    assert not Schedule.objects.filter(pk=schedule.id).exists()


def test_save_schedule_needs_for_selected_day_replaces_only_that_day(
    api_client,
    staff_user,
    schedule,
    work_block,
    second_work_block,
):
    authenticate(api_client, staff_user)
    old_day_1_need = create_need(
        schedule=schedule,
        work_block=work_block,
        day_date=DAY_1,
        shift_kind="primary",
        required_people=5,
    )
    day_2_need = create_need(
        schedule=schedule,
        work_block=work_block,
        day_date=DAY_2,
        shift_kind="primary",
        required_people=1,
    )

    response = api_client.post(
        f"/api/v1/rosters/schedules/{schedule.id}/needs/",
        {
            "date": "2026-04-13",
            "needs": [
                {
                    "work_block": second_work_block.id,
                    "primary": True,
                    "extra": True,
                    "required_people": 2,
                }
            ],
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    assert not ScheduleNeed.objects.filter(pk=old_day_1_need.pk).exists()
    assert ScheduleNeed.objects.filter(pk=day_2_need.pk).exists()

    day_1_needs = ScheduleNeed.objects.filter(schedule=schedule, date=DAY_1).order_by("starts_at")
    assert day_1_needs.count() == 2
    primary, extra = list(day_1_needs)
    assert primary.work_block == second_work_block
    assert primary.starts_at == PRIMARY_START
    assert primary.ends_at == PRIMARY_END
    assert primary.required_people == 2
    assert extra.starts_at == EXTRA_START
    assert extra.ends_at == EXTRA_END
    assert extra.required_people == 2


def test_save_manual_assignments_accepts_member_without_availability_response(
    api_client,
    staff_user,
    schedule,
    closed_availability_form,
    work_block,
    member_one,
    member_two,
):
    authenticate(api_client, staff_user)
    primary_need = create_need(schedule=schedule, work_block=work_block, day_date=DAY_1, shift_kind="primary")
    extra_need = create_need(schedule=schedule, work_block=work_block, day_date=DAY_1, shift_kind="extra")

    # member_two специально не отправлял доступность, но администратор должен иметь возможность
    # добавить его вручную при редактировании графика.
    create_slot(
        form=closed_availability_form,
        membership=member_one,
        day_date=DAY_1,
        shift_kind="primary",
        available=True,
    )

    response = api_client.post(
        f"/api/v1/rosters/schedules/{schedule.id}/assignments/",
        {
            "date": "2026-04-13",
            "assignments": [
                {
                    "membership": member_two.id,
                    "work_block": work_block.id,
                    "primary": True,
                    "extra": False,
                },
                {
                    "membership": member_one.id,
                    "work_block": work_block.id,
                    "primary": False,
                    "extra": True,
                },
            ],
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    entries = ScheduleEntry.objects.filter(schedule=schedule, date=DAY_1).order_by("starts_at")
    assert entries.count() == 2
    assert entries.get(starts_at=PRIMARY_START).membership == member_two
    assert entries.get(starts_at=PRIMARY_START).need == primary_need
    assert entries.get(starts_at=EXTRA_START).membership == member_one
    assert entries.get(starts_at=EXTRA_START).need == extra_need


def test_edit_data_returns_day_needs_entries_and_all_active_members(
    api_client,
    staff_user,
    schedule,
    work_block,
    member_one,
    member_two,
):
    authenticate(api_client, staff_user)
    need = create_need(schedule=schedule, work_block=work_block, day_date=DAY_1, shift_kind="primary")
    ScheduleEntry.objects.create(
        schedule=schedule,
        need=need,
        membership=member_one,
        work_block=work_block,
        date=DAY_1,
        starts_at=PRIMARY_START,
        ends_at=PRIMARY_END,
    )

    response = api_client.get(
        f"/api/v1/rosters/schedules/{schedule.id}/edit-data/",
        {"date": "2026-04-13"},
    )

    assert response.status_code == 200, response.data
    assert response.data["selected_date"] == "2026-04-13"
    assert len(response.data["needs"]) == 1
    assert response.data["needs"][0]["work_block_name"] == work_block.name
    assert response.data["needs"][0]["assigned_count"] == 1

    # Для ручного редактирования фронту нужны все активные участники отряда,
    # даже если они не голосовали в форме доступности.
    members = response.data.get("members", [])
    member_ids = {item.get("id") or item.get("membership") or item.get("membership_id") for item in members}
    assert member_one.id in member_ids
    assert member_two.id in member_ids
