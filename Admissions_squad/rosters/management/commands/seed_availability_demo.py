import random
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Role
from squads.models import Squad, SquadMembership
from rosters.models import (
    AvailabilityForm,
    AvailabilityFormDay,
    AvailabilityFormShift,
    AvailabilitySlot,
    WorkBlock,
)


FIRST_NAMES = [
    "Иван", "Пётр", "Алексей", "Дмитрий", "Сергей",
    "Андрей", "Никита", "Максим", "Василий", "Кирилл",
    "Анна", "Мария", "Екатерина", "Анастасия", "Дарья",
    "Полина", "Виктория", "Софья", "Елизавета", "Алина",
]

LAST_NAMES = [
    "Иванов", "Петров", "Сидоров", "Васильев", "Виноградов",
    "Кузнецов", "Смирнов", "Попов", "Соколов", "Морозов",
    "Новиков", "Фёдоров", "Михайлов", "Алексеев", "Лебедев",
]

MIDDLE_NAMES = [
    "Иванович", "Петрович", "Сергеевич", "Александрович", "Дмитриевич",
    "Ивановна", "Петровна", "Сергеевна", "Александровна", "Дмитриевна",
]


class Command(BaseCommand):
    help = (
        "Создаёт тестовых пользователей, добавляет их в отряд, "
        "создаёт закрытую форму доступности и случайно заполняет ответы."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--squad",
            default="Тестовый отряд для графика",
            help="Название отряда.",
        )

        parser.add_argument(
            "--form-title",
            default="Тестовая форма доступности для графика",
            help="Название формы доступности.",
        )

        parser.add_argument(
            "--users",
            type=int,
            default=30,
            help="Сколько тестовых пользователей создать.",
        )

        parser.add_argument(
            "--start",
            default="2026-04-20",
            help="Дата начала формы в формате YYYY-MM-DD.",
        )

        parser.add_argument(
            "--end",
            default="2026-05-03",
            help="Дата окончания формы в формате YYYY-MM-DD.",
        )

        parser.add_argument(
            "--response-rate",
            type=float,
            default=0.85,
            help="Вероятность, что участник вообще ответит на форму. От 0 до 1.",
        )

        parser.add_argument(
            "--availability-rate",
            type=float,
            default=0.65,
            help="Вероятность, что участник выберет 'выйду' по конкретной смене. От 0 до 1.",
        )

        parser.add_argument(
            "--with-extra",
            action="store_true",
            help="Создавать дополнительную смену на каждый день.",
        )

        parser.add_argument(
            "--password",
            default="Test12345!",
            help="Пароль для созданных тестовых пользователей.",
        )

        parser.add_argument(
            "--clear-old-form",
            action="store_true",
            help="Удалить старую форму с таким же названием перед созданием новой.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        users_count = options["users"]

        if users_count < 1:
            raise CommandError("Количество пользователей должно быть больше 0.")

        period_start = self.parse_date(options["start"])
        period_end = self.parse_date(options["end"])

        if period_end < period_start:
            raise CommandError("Дата окончания не может быть раньше даты начала.")

        response_rate = options["response_rate"]
        availability_rate = options["availability_rate"]

        if not 0 <= response_rate <= 1:
            raise CommandError("--response-rate должен быть от 0 до 1.")

        if not 0 <= availability_rate <= 1:
            raise CommandError("--availability-rate должен быть от 0 до 1.")

        squad = self.get_or_create_squad(options["squad"])
        role = Role.get_or_create_default_member_role()

        users = self.create_users(users_count, options["password"])
        memberships = self.create_memberships(users, squad, role)

        self.create_work_blocks(squad)

        if options["clear_old_form"]:
            AvailabilityForm.objects.filter(
                squad=squad,
                title=options["form_title"],
            ).delete()

        form = self.create_or_replace_form(
            squad=squad,
            title=options["form_title"],
            period_start=period_start,
            period_end=period_end,
        )

        shifts = self.create_days_and_shifts(
            form=form,
            period_start=period_start,
            period_end=period_end,
            with_extra=options["with_extra"],
        )

        stats = self.fill_random_availability(
            memberships=memberships,
            shifts=shifts,
            response_rate=response_rate,
            availability_rate=availability_rate,
        )

        self.stdout.write(self.style.SUCCESS("Тестовые данные созданы."))
        self.stdout.write(f"Отряд: {squad.name} ID={squad.id}")
        self.stdout.write(f"Форма: {form.title} ID={form.id}")
        self.stdout.write(f"Период: {form.period_start} — {form.period_end}")
        self.stdout.write(f"Пользователей в отряде: {len(memberships)}")
        self.stdout.write(f"Смен в форме: {len(shifts)}")
        self.stdout.write(f"Ответили участников: {stats['responded']}")
        self.stdout.write(f"Не ответили участников: {stats['not_responded']}")
        self.stdout.write(f"Создано слотов доступности: {stats['slots']}")
        self.stdout.write("")
        self.stdout.write("Логины пользователей:")
        self.stdout.write("demo_av_001@students.dvfu.ru ...")
        self.stdout.write(f"Пароль: {options['password']}")

    def parse_date(self, value):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CommandError(f"Некорректная дата: {value}. Используй YYYY-MM-DD.") from exc

    def get_or_create_squad(self, squad_name):
        squad, created = Squad.objects.get_or_create(
            name=squad_name,
            defaults={
                "description": "Тестовый отряд для проверки доступности и графика.",
                "regional_office": "Приморское РО",
                "region": "Приморский край",
                "employer": 'ФГАОУ ВО "ДВФУ"',
                "lso_directions": "Студенческие сервисные отряды",
            },
        )

        if created:
            self.stdout.write(f"Создан отряд: {squad.name}")
        else:
            self.stdout.write(f"Используется существующий отряд: {squad.name}")

        return squad

    def create_users(self, users_count, password):
        User = get_user_model()
        users = []

        for index in range(1, users_count + 1):
            number = str(index).zfill(3)
            username = f"demo_av_{number}"
            email = f"{username}@students.dvfu.ru"

            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            middle_name = random.choice(MIDDLE_NAMES)

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "middle_name": middle_name,
                    "birth_day": date(2002, random.randint(1, 12), random.randint(1, 28)),
                    "gender": random.choice(["male", "female"]),
                    "is_active": True,
                },
            )

            if created:
                user.set_password(password)
                user.save(update_fields=["password"])
            else:
                changed_fields = []

                if user.username != username:
                    user.username = username
                    changed_fields.append("username")

                if not user.first_name:
                    user.first_name = first_name
                    changed_fields.append("first_name")

                if not user.last_name:
                    user.last_name = last_name
                    changed_fields.append("last_name")

                if not user.middle_name:
                    user.middle_name = middle_name
                    changed_fields.append("middle_name")

                if changed_fields:
                    user.save(update_fields=changed_fields)

            users.append(user)

        return users

    def create_memberships(self, users, squad, role):
        memberships = []

        for index, user in enumerate(users, start=1):
            active_membership = (
                SquadMembership.objects
                .filter(user=user, is_active=True)
                .select_related("squad")
                .first()
            )

            if active_membership:
                if active_membership.squad_id != squad.id:
                    active_membership.squad = squad
                    active_membership.role = role
                    active_membership.ticket_number = f"TEST-{index:04d}"
                    active_membership.save(
                        update_fields=["squad", "role", "ticket_number"],
                    )
                else:
                    if active_membership.role_id != role.id:
                        active_membership.role = role
                        active_membership.save(update_fields=["role"])

                memberships.append(active_membership)
                continue

            membership = SquadMembership.objects.create(
                user=user,
                squad=squad,
                role=role,
                ticket_number=f"TEST-{index:04d}",
                university='ФГАОУ ВО "ДВФУ"',
                is_active=True,
            )
            memberships.append(membership)

        return memberships

    def create_work_blocks(self, squad):
        blocks = [
            ("REG", "Регистрация абитуриентов"),
            ("DOC", "Работа с документами"),
            ("INFO", "Информационная стойка"),
            ("FLOW", "Сопровождение потока"),
        ]

        for code, name in blocks:
            WorkBlock.objects.get_or_create(
                squad=squad,
                code=code,
                defaults={
                    "name": name,
                    "is_active": True,
                },
            )

    def create_or_replace_form(self, squad, title, period_start, period_end):
        existing_form = (
            AvailabilityForm.objects
            .filter(squad=squad, title=title)
            .first()
        )

        if existing_form:
            existing_form.days.all().delete()
            existing_form.period_start = period_start
            existing_form.period_end = period_end
            existing_form.response_deadline = timezone.now() - timedelta(hours=1)
            existing_form.status = "closed"
            existing_form.save(
                update_fields=[
                    "period_start",
                    "period_end",
                    "response_deadline",
                    "status",
                ],
            )
            return existing_form

        creator = self.get_creator_user()

        return AvailabilityForm.objects.create(
            squad=squad,
            title=title,
            period_start=period_start,
            period_end=period_end,
            response_deadline=timezone.now() - timedelta(hours=1),
            status="closed",
            created_by=creator,
        )

    def get_creator_user(self):
        User = get_user_model()

        return (
            User.objects.filter(is_superuser=True).first()
            or User.objects.filter(is_staff=True).first()
            or User.objects.first()
        )

    def create_days_and_shifts(self, form, period_start, period_end, with_extra):
        shifts = []
        current = period_start

        while current <= period_end:
            day = AvailabilityFormDay.objects.create(
                form=form,
                date=current,
            )

            primary_shift = AvailabilityFormShift.objects.create(
                day=day,
                shift_kind="primary",
                title="Основная смена",
                starts_at=time(9, 0),
                ends_at=time(15, 0),
                is_active=True,
            )
            shifts.append(primary_shift)

            if with_extra:
                extra_shift = AvailabilityFormShift.objects.create(
                    day=day,
                    shift_kind="extra",
                    title="Дополнительная смена",
                    starts_at=time(15, 0),
                    ends_at=time(20, 0),
                    is_active=True,
                )
                shifts.append(extra_shift)

            current += timedelta(days=1)

        return shifts

    def fill_random_availability(
        self,
        memberships,
        shifts,
        response_rate,
        availability_rate,
    ):
        AvailabilitySlot.objects.filter(
            membership__in=memberships,
            shift__in=shifts,
        ).delete()

        responded = 0
        not_responded = 0
        slots_count = 0

        comments_available = [
            "",
            "",
            "",
            "Могу выйти без ограничений",
            "Удобно в это время",
        ]

        comments_unavailable = [
            "",
            "",
            "Не могу",
            "Занят в это время",
            "Неудобная смена",
        ]

        for membership in memberships:
            has_response = random.random() <= response_rate

            if not has_response:
                not_responded += 1
                continue

            responded += 1

            for shift in shifts:
                is_available = random.random() <= availability_rate

                comment = random.choice(
                    comments_available if is_available else comments_unavailable
                )

                AvailabilitySlot.objects.create(
                    shift=shift,
                    membership=membership,
                    is_available=is_available,
                    comment=comment,
                )

                slots_count += 1

        return {
            "responded": responded,
            "not_responded": not_responded,
            "slots": slots_count,
        }