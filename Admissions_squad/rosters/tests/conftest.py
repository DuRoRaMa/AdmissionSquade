from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser, Role
from squads.models import Squad, SquadMembership
from rosters.models import (
    AvailabilityForm,
    AvailabilityFormDay,
    AvailabilityFormShift,
    AvailabilitySlot,
    Schedule,
    ScheduleNeed,
    WorkBlock,
)


TEST_PASSWORD = "StrongTestPassword123"
PRIMARY_START = time(9, 0)
PRIMARY_END = time(18, 0)
EXTRA_START = time(18, 0)
EXTRA_END = time(21, 0)
DAY_1 = date(2026, 4, 13)
DAY_2 = date(2026, 4, 14)


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def staff_user(db) -> CustomUser:
    return CustomUser.objects.create_user(
        email="admin@dvfu.ru",
        username="admin",
        password=TEST_PASSWORD,
        first_name="Админ",
        last_name="Системный",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def squad(db) -> Squad:
    return Squad.objects.create(name="Тестовый отряд")


@pytest.fixture
def member_role(db) -> Role:
    return Role.objects.create(
        name="Тестовый участник",
        slug="test_member",
        permissions=[
            "availability.respond_own",
            "roster.view_own",
        ],
    )


@pytest.fixture
def roster_manager_role(db) -> Role:
    return Role.objects.create(
        name="Тестовый руководитель графиков",
        slug="test_roster_manager",
        permissions=[
            "availability.manage",
            "roster.manage",
            "roster.publish",
            "roster.view_all",
        ],
    )


def create_user(index: int, *, first_name: str | None = None, last_name: str | None = None) -> CustomUser:
    return CustomUser.objects.create_user(
        email=f"user{index}@students.dvfu.ru",
        username=f"user{index}",
        password=TEST_PASSWORD,
        first_name=first_name or f"Имя{index}",
        last_name=last_name or f"Фамилия{index}",
    )


def create_membership(
    *,
    user: CustomUser,
    squad: Squad,
    role: Role,
    active: bool = True,
) -> SquadMembership:
    return SquadMembership.objects.create(
        user=user,
        squad=squad,
        role=role,
        is_active=active,
    )


@pytest.fixture
def member_one(db, squad, member_role) -> SquadMembership:
    return create_membership(
        user=create_user(1, first_name="Анна", last_name="Алексеева"),
        squad=squad,
        role=member_role,
    )


@pytest.fixture
def member_two(db, squad, member_role) -> SquadMembership:
    return create_membership(
        user=create_user(2, first_name="Борис", last_name="Борисов"),
        squad=squad,
        role=member_role,
    )


@pytest.fixture
def member_three(db, squad, member_role) -> SquadMembership:
    return create_membership(
        user=create_user(3, first_name="Виктор", last_name="Васильев"),
        squad=squad,
        role=member_role,
    )


@pytest.fixture
def manager_membership(db, staff_user, squad, roster_manager_role) -> SquadMembership:
    return create_membership(user=staff_user, squad=squad, role=roster_manager_role)


@pytest.fixture
def work_block(db, squad) -> WorkBlock:
    return WorkBlock.objects.create(
        squad=squad,
        code="MAIN",
        name="Основной блок",
        is_active=True,
    )


@pytest.fixture
def second_work_block(db, squad) -> WorkBlock:
    return WorkBlock.objects.create(
        squad=squad,
        code="CONS",
        name="Консультации",
        is_active=True,
    )


@pytest.fixture
def inactive_work_block(db, squad) -> WorkBlock:
    return WorkBlock.objects.create(
        squad=squad,
        code="OLD",
        name="Старый блок",
        is_active=False,
    )


def create_availability_form(
    *,
    squad: Squad,
    created_by: CustomUser,
    status: str = "closed",
    period_start: date = DAY_1,
    period_end: date = DAY_2,
) -> AvailabilityForm:
    form = AvailabilityForm.objects.create(
        squad=squad,
        title="Форма доступности",
        period_start=period_start,
        period_end=period_end,
        response_deadline=timezone.now() + timedelta(days=7),
        status=status,
        created_by=created_by,
    )

    current = period_start
    while current <= period_end:
        day = AvailabilityFormDay.objects.create(form=form, date=current)
        AvailabilityFormShift.objects.create(
            day=day,
            shift_kind="primary",
            title="Основная смена",
            starts_at=PRIMARY_START,
            ends_at=PRIMARY_END,
            is_active=True,
        )
        AvailabilityFormShift.objects.create(
            day=day,
            shift_kind="extra",
            title="Дополнительная смена",
            starts_at=EXTRA_START,
            ends_at=EXTRA_END,
            is_active=True,
        )
        current += timedelta(days=1)

    return form


@pytest.fixture
def closed_availability_form(db, squad, staff_user) -> AvailabilityForm:
    return create_availability_form(squad=squad, created_by=staff_user, status="closed")


@pytest.fixture
def open_availability_form(db, squad, staff_user) -> AvailabilityForm:
    return create_availability_form(squad=squad, created_by=staff_user, status="open")


def get_shift(form: AvailabilityForm, day_date: date, shift_kind: str) -> AvailabilityFormShift:
    return AvailabilityFormShift.objects.get(
        day__form=form,
        day__date=day_date,
        shift_kind=shift_kind,
    )


def create_slot(
    *,
    form: AvailabilityForm,
    membership: SquadMembership,
    day_date: date,
    shift_kind: str,
    available: bool = True,
) -> AvailabilitySlot:
    return AvailabilitySlot.objects.create(
        shift=get_shift(form, day_date, shift_kind),
        membership=membership,
        is_available=available,
    )


def create_schedule(
    *,
    squad: Squad,
    form: AvailabilityForm,
    created_by: CustomUser,
    title: str = "График",
) -> Schedule:
    return Schedule.objects.create(
        squad=squad,
        availability_form=form,
        title=title,
        period_start=form.period_start,
        period_end=form.period_end,
        created_by=created_by,
    )


@pytest.fixture
def schedule(db, squad, closed_availability_form, staff_user) -> Schedule:
    return create_schedule(squad=squad, form=closed_availability_form, created_by=staff_user)


def create_need(
    *,
    schedule: Schedule,
    work_block: WorkBlock,
    day_date: date = DAY_1,
    shift_kind: str = "primary",
    required_people: int = 1,
) -> ScheduleNeed:
    starts_at = PRIMARY_START if shift_kind == "primary" else EXTRA_START
    ends_at = PRIMARY_END if shift_kind == "primary" else EXTRA_END
    return ScheduleNeed.objects.create(
        schedule=schedule,
        date=day_date,
        work_block=work_block,
        starts_at=starts_at,
        ends_at=ends_at,
        required_people=required_people,
    )


def authenticate(client: APIClient, user: CustomUser) -> APIClient:
    client.force_authenticate(user=user)
    return client


def list_payload(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return data["results"]
    return []
