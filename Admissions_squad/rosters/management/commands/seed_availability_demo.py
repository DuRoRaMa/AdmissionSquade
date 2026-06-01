from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser, Role
from rosters.models import (
    AvailabilityForm,
    AvailabilityFormDay,
    AvailabilityFormShift,
    AvailabilitySlot,
    Schedule,
    ScheduleEntry,
    WorkBlock,
)
from squads.models import Squad, SquadMembership


TEST_PASSWORD = "Test12345!"


WORK_BLOCKS = [
    {
        "code": "KC",
        "name": "КЦ",
    },
    {
        "code": "OCHN",
        "name": "Очный прием",
    },
    {
        "code": "COD",
        "name": "ЦОД",
    },
    {
        "code": "RES",
        "name": "Ресепшен",
    },
    {
        "code": "ARCH",
        "name": "Архив",
    },
]


MEMBERS = [
    {
        "email": "ivanov.test@students.dvfu.ru",
        "username": "ivanov_test",
        "last_name": "Иванов",
        "first_name": "Алексей",
        "middle_name": "Сергеевич",
        "phone": "+79000000001",
        "preferred_block": "KC",
    },
    {
        "email": "petrova.test@students.dvfu.ru",
        "username": "petrova_test",
        "last_name": "Петрова",
        "first_name": "Мария",
        "middle_name": "Андреевна",
        "phone": "+79000000002",
        "preferred_block": "KC",
    },
    {
        "email": "morozov.test@students.dvfu.ru",
        "username": "morozov_test",
        "last_name": "Морозов",
        "first_name": "Илья",
        "middle_name": "Павлович",
        "phone": "+79000000003",
        "preferred_block": "KC",
    },
    {
        "email": "sidorov.test@students.dvfu.ru",
        "username": "sidorov_test",
        "last_name": "Сидоров",
        "first_name": "Никита",
        "middle_name": "Олегович",
        "phone": "+79000000004",
        "preferred_block": "OCHN",
    },
    {
        "email": "vasilieva.test@students.dvfu.ru",
        "username": "vasilieva_test",
        "last_name": "Васильева",
        "first_name": "Ксения",
        "middle_name": "Дмитриевна",
        "phone": "+79000000005",
        "preferred_block": "OCHN",
    },
    {
        "email": "smirnova.test@students.dvfu.ru",
        "username": "smirnova_test",
        "last_name": "Смирнова",
        "first_name": "Анна",
        "middle_name": "Игоревна",
        "phone": "+79000000006",
        "preferred_block": "COD",
    },
    {
        "email": "belova.test@students.dvfu.ru",
        "username": "belova_test",
        "last_name": "Белова",
        "first_name": "Полина",
        "middle_name": "Романовна",
        "phone": "+79000000007",
        "preferred_block": "COD",
    },
    {
        "email": "orlova.test@students.dvfu.ru",
        "username": "orlova_test",
        "last_name": "Орлова",
        "first_name": "София",
        "middle_name": "Владимировна",
        "phone": "+79000000008",
        "preferred_block": "RES",
    },
    {
        "email": "kuznecova.test@students.dvfu.ru",
        "username": "kuznecova_test",
        "last_name": "Кузнецова",
        "first_name": "Дарья",
        "middle_name": "Алексеевна",
        "phone": "+79000000009",
        "preferred_block": None,
    },
    {
        "email": "novikov.test@students.dvfu.ru",
        "username": "novikov_test",
        "last_name": "Новиков",
        "first_name": "Артем",
        "middle_name": "Максимович",
        "phone": "+79000000010",
        "preferred_block": None,
    },
]


class Command(BaseCommand):
    help = "Создает тестовые данные для проверки генерации графика по выбранным блокам работы."

    @transaction.atomic
    def handle(self, *args, **options):
        roles = self.create_roles()
        squad = self.create_squad()
        work_blocks = self.create_work_blocks(squad)

        commander = self.create_commander()
        self.create_membership(
            user=commander,
            squad=squad,
            role=roles["commander"],
        )

        memberships = []

        for member_data in MEMBERS:
            user = self.create_user(member_data)
            membership = self.create_membership(
                user=user,
                squad=squad,
                role=roles["member"],
            )
            memberships.append(
                {
                    "membership": membership,
                    "preferred_block": member_data["preferred_block"],
                }
            )

        form = self.create_availability_form(
            squad=squad,
            created_by=commander,
        )

        shifts = self.create_form_days_and_shifts(form)
        self.create_availability_answers(
            shifts=shifts,
            memberships=memberships,
            work_blocks=work_blocks,
        )
        self.create_history_for_rest_priority(
            squad=squad,
            commander=commander,
            work_blocks=work_blocks,
            memberships=memberships,
            period_start=form.period_start,
        )

        self.stdout.write(self.style.SUCCESS("Тестовые данные созданы."))
        self.stdout.write("")
        self.stdout.write(f"Отряд: {squad.name}")
        self.stdout.write(f"Форма доступности: {form.title}")
        self.stdout.write(f"Период формы: {form.period_start} — {form.period_end}")
        self.stdout.write(f"Статус формы: {form.status}")
        self.stdout.write("")
        self.stdout.write("Пользователь для входа командиром:")
        self.stdout.write(f"email: {commander.email}")
        self.stdout.write(f"password: {TEST_PASSWORD}")
        self.stdout.write("")
        self.stdout.write("Рекомендуемые потребности для проверки генератора:")
        self.stdout.write("1) КЦ — 2 человека, 10:00–18:00")
        self.stdout.write("2) Очный прием — 2 человека, 10:00–18:00")
        self.stdout.write("3) ЦОД — 2 человека, 10:00–18:00")
        self.stdout.write("4) Ресепшен — 1 человек, 10:00–18:00")
        self.stdout.write("")
        self.stdout.write(
            "Если для КЦ поставить потребность 4 человека, генератор должен сначала взять тех, кто выбрал КЦ, "
            "а потом добрать доступных участников без выбранного блока."
        )

    def create_roles(self):
        Role.ensure_system_roles()

        member_role = Role.get_or_create_default_member_role()

        base_user_role = Role.get_or_create_base_user_role()

        commander_role, _ = Role.objects.get_or_create(
            slug="commander",
            defaults={
                "name": "Командир отряда",
                "description": "Тестовая роль командира для управления отрядом, формами и графиками.",
                "parent": base_user_role,
                "permissions": [
                    "squad.view",
                    "squad.manage",
                    "membership.join_own",
                    "membership.manage",
                    "availability.respond_own",
                    "availability.manage",
                    "roster.view_own",
                    "roster.view_all",
                    "roster.manage",
                    "roster.publish",
                    "fee.view_own",
                    "fee.manage",
                ],
                "is_system": False,
            },
        )

        changed = False

        required_permissions = [
            "squad.view",
            "squad.manage",
            "membership.join_own",
            "membership.manage",
            "availability.respond_own",
            "availability.manage",
            "roster.view_own",
            "roster.view_all",
            "roster.manage",
            "roster.publish",
            "fee.view_own",
            "fee.manage",
        ]

        if sorted(commander_role.permissions or []) != sorted(required_permissions):
            commander_role.permissions = required_permissions
            changed = True

        if commander_role.parent_id != base_user_role.id:
            commander_role.parent = base_user_role
            changed = True

        if changed:
            commander_role.save()

        return {
            "member": member_role,
            "commander": commander_role,
        }

    def create_squad(self):
        squad, _ = Squad.objects.update_or_create(
            name="Тестовый отряд для генерации",
            defaults={
                "description": "Отряд для проверки распределения участников по выбранным блокам работы.",
                "regional_office": "Приморское РО",
                "region": "Приморский край",
                "employer": 'ФГАОУ ВО "ДВФУ"',
                "lso_directions": "Студенческие сервисные отряды",
            },
        )

        return squad

    def create_work_blocks(self, squad):
        result = {}

        for block_data in WORK_BLOCKS:
            block, _ = WorkBlock.objects.update_or_create(
                squad=squad,
                code=block_data["code"],
                defaults={
                    "name": block_data["name"],
                    "is_active": True,
                },
            )

            result[block.code] = block

        return result

    def create_commander(self):
        commander_data = {
            "email": "commander.test@dvfu.ru",
            "username": "commander_test",
            "last_name": "Командирова",
            "first_name": "Елена",
            "middle_name": "Викторовна",
            "phone": "+79000000000",
        }

        commander = self.create_user(commander_data)
        commander.is_staff = True
        commander.save(update_fields=["is_staff"])

        return commander

    def create_user(self, data):
        user, _ = CustomUser.objects.get_or_create(
            email=data["email"],
            defaults={
                "username": data["username"],
                "last_name": data["last_name"],
                "first_name": data["first_name"],
                "middle_name": data["middle_name"],
                "phone": data["phone"],
                "birth_day": "2002-01-01",
            },
        )

        user.username = data["username"]
        user.last_name = data["last_name"]
        user.first_name = data["first_name"]
        user.middle_name = data["middle_name"]
        user.phone = data["phone"]
        user.birth_day = "2002-01-01"
        user.is_active = True
        user.is_blocked = False
        user.set_password(TEST_PASSWORD)
        user.save()

        return user

    def create_membership(self, user, squad, role):
        membership, _ = SquadMembership.objects.get_or_create(
            user=user,
            defaults={
                "squad": squad,
                "role": role,
                "is_active": True,
                "university": 'ФГАОУ ВО "ДВФУ"',
            },
        )

        membership.squad = squad
        membership.role = role
        membership.is_active = True
        membership.university = 'ФГАОУ ВО "ДВФУ"'
        membership.save()

        return membership

    def create_availability_form(self, squad, created_by):
        today = timezone.localdate()
        period_start = today + timedelta(days=1)
        period_end = period_start + timedelta(days=2)

        form, _ = AvailabilityForm.objects.update_or_create(
            squad=squad,
            title="Тестовая форма доступности для генерации",
            defaults={
                "period_start": period_start,
                "period_end": period_end,
                "response_deadline": timezone.now() - timedelta(hours=1),
                "allow_work_block_choice": True,
                "status": "closed",
                "created_by": created_by,
            },
        )

        return form

    def create_form_days_and_shifts(self, form):
        expected_dates = [
            form.period_start + timedelta(days=offset)
            for offset in range((form.period_end - form.period_start).days + 1)
        ]

        form.days.exclude(date__in=expected_dates).delete()

        shifts = []

        for current_date in expected_dates:
            day, _ = AvailabilityFormDay.objects.get_or_create(
                form=form,
                date=current_date,
            )

            primary_shift, _ = AvailabilityFormShift.objects.update_or_create(
                day=day,
                shift_kind="primary",
                defaults={
                    "title": "Основная смена",
                    "starts_at": time(10, 0),
                    "ends_at": time(18, 0),
                    "is_active": True,
                },
            )

            extra_shift, _ = AvailabilityFormShift.objects.update_or_create(
                day=day,
                shift_kind="extra",
                defaults={
                    "title": "Дополнительная смена",
                    "starts_at": time(18, 0),
                    "ends_at": time(21, 0),
                    "is_active": True,
                },
            )

            shifts.append(primary_shift)
            shifts.append(extra_shift)

        return shifts

    def create_availability_answers(self, shifts, memberships, work_blocks):
        for shift in shifts:
            for item in memberships:
                membership = item["membership"]
                preferred_block_code = item["preferred_block"]

                is_available = self.is_member_available(
                    membership=membership,
                    shift=shift,
                    preferred_block_code=preferred_block_code,
                )

                preferred_work_block = None

                if is_available and preferred_block_code:
                    preferred_work_block = work_blocks[preferred_block_code]

                AvailabilitySlot.objects.update_or_create(
                    shift=shift,
                    membership=membership,
                    defaults={
                        "is_available": is_available,
                        "preferred_work_block": preferred_work_block,
                    },
                )

    def is_member_available(self, membership, shift, preferred_block_code):
        """
        Основная смена:
        почти все доступны, чтобы было видно распределение по блокам.

        Дополнительная смена:
        доступны только несколько человек, чтобы можно было отдельно проверить вечернюю смену.
        """
        email = membership.user.email

        if shift.shift_kind == "extra":
            return email in {
                "kuznecova.test@students.dvfu.ru",
                "novikov.test@students.dvfu.ru",
                "orlova.test@students.dvfu.ru",
                "petrova.test@students.dvfu.ru",
            }

        if shift.day.date == shift.day.form.period_start + timedelta(days=1):
            return email not in {
                "ivanov.test@students.dvfu.ru",
                "sidorov.test@students.dvfu.ru",
            }

        return True

    def create_history_for_rest_priority(
        self,
        squad,
        commander,
        work_blocks,
        memberships,
        period_start,
    ):
        """
        Создает несколько старых назначений, чтобы можно было проверить приоритет:
        те, кто давно не выходил, должны подниматься выше внутри своей группы.
        """
        history_schedule, _ = Schedule.objects.update_or_create(
            squad=squad,
            title="Тестовая история прошлых смен",
            defaults={
                "availability_form": None,
                "period_start": period_start - timedelta(days=7),
                "period_end": period_start - timedelta(days=1),
                "status": "archived",
                "created_by": commander,
            },
        )

        history_schedule.entries.all().delete()

        membership_by_email = {
            item["membership"].user.email: item["membership"]
            for item in memberships
        }

        history_items = [
            {
                "email": "ivanov.test@students.dvfu.ru",
                "days_before": 1,
                "work_block": "KC",
            },
            {
                "email": "sidorov.test@students.dvfu.ru",
                "days_before": 2,
                "work_block": "OCHN",
            },
            {
                "email": "smirnova.test@students.dvfu.ru",
                "days_before": 5,
                "work_block": "COD",
            },
            {
                "email": "orlova.test@students.dvfu.ru",
                "days_before": 4,
                "work_block": "RES",
            },
        ]

        for item in history_items:
            membership = membership_by_email[item["email"]]
            work_block = work_blocks[item["work_block"]]
            entry_date = period_start - timedelta(days=item["days_before"])

            ScheduleEntry.objects.create(
                schedule=history_schedule,
                need=None,
                membership=membership,
                work_block=work_block,
                date=entry_date,
                starts_at=time(10, 0),
                ends_at=time(18, 0),
                status="attended",
            )
