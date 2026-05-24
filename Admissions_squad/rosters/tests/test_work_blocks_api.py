from __future__ import annotations

import pytest

from rosters.models import WorkBlock
from .conftest import authenticate, list_payload


pytestmark = pytest.mark.django_db


def test_work_blocks_list_hides_inactive_by_default(
    api_client,
    staff_user,
    squad,
    work_block,
    inactive_work_block,
):
    authenticate(api_client, staff_user)

    response = api_client.get("/api/v1/rosters/work-blocks/", {"squad": squad.id})

    assert response.status_code == 200, response.data
    codes = {item["code"] for item in list_payload(response.data)}
    assert work_block.code in codes
    assert inactive_work_block.code not in codes


def test_work_blocks_list_can_include_inactive(
    api_client,
    staff_user,
    squad,
    work_block,
    inactive_work_block,
):
    authenticate(api_client, staff_user)

    response = api_client.get(
        "/api/v1/rosters/work-blocks/",
        {"squad": squad.id, "include_inactive": "true"},
    )

    assert response.status_code == 200, response.data
    codes = {item["code"] for item in list_payload(response.data)}
    assert work_block.code in codes
    assert inactive_work_block.code in codes


def test_work_block_create_and_deactivate(
    api_client,
    staff_user,
    squad,
):
    authenticate(api_client, staff_user)

    create_response = api_client.post(
        "/api/v1/rosters/work-blocks/",
        {
            "squad": squad.id,
            "code": "DOC",
            "name": "Работа с документами",
            "is_active": True,
        },
        format="json",
    )

    assert create_response.status_code == 201, create_response.data
    block_id = create_response.data["id"]
    assert WorkBlock.objects.get(pk=block_id).is_active is True

    patch_response = api_client.patch(
        f"/api/v1/rosters/work-blocks/{block_id}/",
        {"is_active": False},
        format="json",
    )

    assert patch_response.status_code == 200, patch_response.data
    block = WorkBlock.objects.get(pk=block_id)
    assert block.is_active is False

    list_response = api_client.get("/api/v1/rosters/work-blocks/", {"squad": squad.id})
    codes = {item["code"] for item in list_payload(list_response.data)}
    assert "DOC" not in codes
