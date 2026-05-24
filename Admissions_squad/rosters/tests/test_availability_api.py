from __future__ import annotations

import pytest

from rosters.models import AvailabilityForm, AvailabilitySlot
from .conftest import DAY_1, authenticate, get_shift, list_payload


pytestmark = pytest.mark.django_db


def test_admin_can_create_open_close_availability_form(api_client, staff_user, squad):
    authenticate(api_client, staff_user)

    payload = {
        "squad": squad.id,
        "title": "Апрельская форма",
        "period_start": "2026-04-13",
        "period_end": "2026-04-14",
        "response_deadline": "2026-04-10T23:59:00+10:00",
        "days": [
            {
                "date": "2026-04-13",
                "shifts": [
                    {
                        "shift_kind": "primary",
                        "title": "Основная смена",
                        "starts_at": "09:00:00",
                        "ends_at": "18:00:00",
                        "is_active": True,
                    },
                    {
                        "shift_kind": "extra",
                        "title": "Дополнительная смена",
                        "starts_at": "18:00:00",
                        "ends_at": "21:00:00",
                        "is_active": True,
                    },
                ],
            },
            {
                "date": "2026-04-14",
                "shifts": [
                    {
                        "shift_kind": "primary",
                        "title": "Основная смена",
                        "starts_at": "09:00:00",
                        "ends_at": "18:00:00",
                        "is_active": True,
                    }
                ],
            },
        ],
    }

    create_response = api_client.post("/api/v1/rosters/forms/", payload, format="json")

    assert create_response.status_code == 201, create_response.data
    form = AvailabilityForm.objects.get(pk=create_response.data["id"])
    assert form.status == "draft"
    assert form.days.count() == 2
    assert form.days.get(date=DAY_1).shifts.count() == 2

    open_response = api_client.post(f"/api/v1/rosters/forms/{form.id}/open/")
    assert open_response.status_code == 200, open_response.data
    form.refresh_from_db()
    assert form.status == "open"

    close_response = api_client.post(f"/api/v1/rosters/forms/{form.id}/close/")
    assert close_response.status_code == 200, close_response.data
    form.refresh_from_db()
    assert form.status == "closed"


def test_member_can_submit_availability_and_second_submit_replaces_previous(
    api_client,
    open_availability_form,
    member_one,
):
    authenticate(api_client, member_one.user)
    primary = get_shift(open_availability_form, DAY_1, "primary")
    extra = get_shift(open_availability_form, DAY_1, "extra")

    first_response = api_client.post(
        f"/api/v1/rosters/forms/{open_availability_form.id}/submit/",
        {
            "slots": [
                {"shift_id": primary.id, "is_available": True},
                {"shift_id": extra.id, "is_available": False},
            ]
        },
        format="json",
    )

    assert first_response.status_code == 200, first_response.data
    assert AvailabilitySlot.objects.filter(membership=member_one).count() == 2

    second_response = api_client.post(
        f"/api/v1/rosters/forms/{open_availability_form.id}/submit/",
        {
            "slots": [
                {"shift_id": primary.id, "is_available": False},
            ]
        },
        format="json",
    )

    assert second_response.status_code == 200, second_response.data
    slots = AvailabilitySlot.objects.filter(membership=member_one)
    assert slots.count() == 1
    assert slots.get().shift_id == primary.id
    assert slots.get().is_available is False


def test_submit_availability_rejects_duplicate_shift(api_client, open_availability_form, member_one):
    authenticate(api_client, member_one.user)
    primary = get_shift(open_availability_form, DAY_1, "primary")

    response = api_client.post(
        f"/api/v1/rosters/forms/{open_availability_form.id}/submit/",
        {
            "slots": [
                {"shift_id": primary.id, "is_available": True},
                {"shift_id": primary.id, "is_available": False},
            ]
        },
        format="json",
    )

    assert response.status_code == 400


def test_availability_responses_include_responded_and_not_responded_members(
    api_client,
    staff_user,
    open_availability_form,
    member_one,
    member_two,
):
    authenticate(api_client, staff_user)
    primary = get_shift(open_availability_form, DAY_1, "primary")
    AvailabilitySlot.objects.create(shift=primary, membership=member_one, is_available=True)

    response = api_client.get(f"/api/v1/rosters/forms/{open_availability_form.id}/responses/")

    assert response.status_code == 200, response.data
    members = response.data["members"]
    by_membership = {item["membership_id"]: item for item in members}
    assert by_membership[member_one.id]["has_response"] is True
    assert by_membership[member_two.id]["has_response"] is False


def test_availability_responses_export_returns_xlsx(api_client, staff_user, open_availability_form):
    authenticate(api_client, staff_user)

    response = api_client.get(f"/api/v1/rosters/forms/{open_availability_form.id}/responses/export/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response.content.startswith(b"PK")
