from __future__ import annotations

import re

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField


GENDER = [
    ("male", "Мужской"),
    ("female", "Женский"),
]

FACULTY = [
    ("IMKT", "ИМКТ"),
    ("VI", "ВИ"),
    ("PISH", "ПИШ"),
    ("SHIGN", "ШИГН"),
    ("IMO", "ИМО"),
    ("PI", "ПИ"),
    ("ITPM", "ИТПМ"),
    ("SHMINZ", "ШМИНЖ"),
    ("IFKS", "ИФКС"),
    ("USH", "ЮШ"),
    ("SHEM", "ШЭМ"),
    ("SHP", "ШП"),
]

STUDY_FORM = [
    ("Full-time", "Очная"),
    ("Full-part-time", "Очно-заочная"),
    ("Part-time", "Заочная"),
]

ROLE_PERMISSION_GROUPS = [
    {
        "key": "squads",
        "title": "Отряды",
        "permissions": [
            {
                "code": "squad.view",
                "name": "Просмотр отрядов",
                "description": "Просмотр карточек и состава отрядов.",
            },
            {
                "code": "squad.manage",
                "name": "Управление отрядом",
                "description": "Редактирование данных отряда.",
            },
        ],
    },
    {
        "key": "memberships",
        "title": "Участники",
        "permissions": [
            {
                "code": "membership.create",
                "name": "Добавление участников",
                "description": "Создание нового членства в отряде.",
            },
            {
                "code": "membership.view_all",
                "name": "Просмотр участников",
                "description": "Просмотр всех участников отряда и их карточек.",
            },
            {
                "code": "membership.update",
                "name": "Изменение участника",
                "description": "Изменение роли, билета и других полей членства.",
            },
            {
                "code": "membership.deactivate",
                "name": "Исключение участника",
                "description": "Деактивация членства участника.",
            },
        ],
    },
    {
        "key": "fees",
        "title": "Взносы",
        "permissions": [
            {
                "code": "fee.manage",
                "name": "Управление взносами",
                "description": "Создание, изменение и удаление взносов.",
            },
        ],
    },
    {
        "key": "availability",
        "title": "Доступность",
        "permissions": [
            {
                "code": "availability.view_all",
                "name": "Просмотр доступностей",
                "description": "Просмотр ответов всех участников по доступности.",
            },
            {
                "code": "availability.manage",
                "name": "Управление формами доступности",
                "description": "Создание и настройка форм доступности.",
            },
            {
                "code": "availability.respond_own",
                "name": "Заполнение своей доступности",
                "description": "Отправка собственной формы доступности.",
            },
        ],
    },
    {
        "key": "rosters",
        "title": "График",
        "permissions": [
            {
                "code": "roster.view_all",
                "name": "Просмотр общего графика",
                "description": "Просмотр полного графика и смен отряда.",
            },
            {
                "code": "roster.view_own",
                "name": "Просмотр своего графика",
                "description": "Просмотр только своих назначений.",
            },
            {
                "code": "roster.manage",
                "name": "Формирование графика",
                "description": "Создание и редактирование графика.",
            },
            {
                "code": "roster.publish",
                "name": "Публикация графика",
                "description": "Публикация итогового варианта графика.",
            },
        ],
    },
]

ROLE_PERMISSION_INDEX = {
    permission["code"]: permission
    for group in ROLE_PERMISSION_GROUPS
    for permission in group["permissions"]
}
ROLE_PERMISSION_CODES = tuple(sorted(ROLE_PERMISSION_INDEX.keys()))


class CustomUser(AbstractUser):
    email = models.EmailField(
        "Email",
        unique=True,
        error_messages={"unique": "Пользователь с таким Email уже существует."},
    )
    username = models.CharField(
        "Имя пользователя",
        max_length=150,
        unique=True,
        help_text="Обязательное поле. Не более 150 символов.",
    )
    middle_name = models.CharField("Отчество", max_length=150, blank=True)
    phone = PhoneNumberField(
        "Номер телефона",
        unique=True,
        max_length=30,
        blank=True,
        null=True,
        region="RU",
        help_text="Формат: +7XXXXXXXXXX",
        error_messages={"unique": "Этот номер телефона уже используется."},
    )
    is_blocked = models.BooleanField("Заблокирован", default=False)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)
    gender = models.CharField("Пол", choices=GENDER, blank=True, null=True)
    birth_day = models.DateField("День рождения", default="2000-01-01")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "username"]

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        db_table = "users"
        ordering = ["-date_joined"]

    def __str__(self):
        name = self.get_full_name()
        return f"{self.email} ({name if name else self.username})"

    def get_full_name(self):
        parts = [self.last_name, self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        return " ".join(filter(None, parts))

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.lower().strip()
            dvfu_email_regex = r"^[a-zA-Z0-9._%+-]+@(?:dvfu\.ru|students\.dvfu\.ru)$"
            if not re.match(dvfu_email_regex, self.email):
                raise ValidationError(
                    {
                        "email": (
                            "Разрешены только email адреса ДВФУ: "
                            "name@dvfu.ru или name@students.dvfu.ru"
                        )
                    }
                )


class Role(models.Model):
    name = models.CharField("Роль пользователя", max_length=50, unique=True)
    slug = models.SlugField("Slug", max_length=50, unique=True)
    description = models.TextField("Описание", blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительская роль",
    )
    permissions = models.JSONField("Права", default=list, blank=True)
    is_system = models.BooleanField("Системная роль", default=False)

    class Meta:
        verbose_name = "Роль в отряде"
        verbose_name_plural = "Роли в отрядах"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @classmethod
    def permission_catalog(cls):
        return ROLE_PERMISSION_GROUPS

    def get_all_permissions(self):
        permissions = set(self.permissions or [])
        current = self.parent
        visited = set()

        while current and current.pk not in visited:
            visited.add(current.pk)
            permissions.update(current.permissions or [])
            current = current.parent

        return sorted(permissions)

    def has_permission(self, permission_code: str) -> bool:
        return permission_code in set(self.get_all_permissions())

    def clean(self):
        super().clean()

        self.slug = (self.slug or "").strip().lower()
        self.permissions = sorted(set(self.permissions or []))

        if not re.fullmatch(r"[a-z0-9_-]+", self.slug):
            raise ValidationError(
                {
                    "slug": (
                        "Slug может содержать только латинские буквы в нижнем регистре, "
                        "цифры, дефис и нижнее подчеркивание."
                    )
                }
            )

        invalid_permissions = sorted(set(self.permissions) - set(ROLE_PERMISSION_CODES))
        if invalid_permissions:
            raise ValidationError(
                {
                    "permissions": (
                        "Обнаружены неизвестные права: "
                        + ", ".join(invalid_permissions)
                    )
                }
            )

        if self.parent_id and self.pk and self.parent_id == self.pk:
            raise ValidationError({"parent": "Роль не может наследоваться сама от себя."})

        current = self.parent
        visited = {self.pk} if self.pk else set()
        while current:
            if current.pk in visited:
                raise ValidationError(
                    {"parent": "Обнаружен циклический граф наследования ролей."}
                )
            if current.pk:
                visited.add(current.pk)
            current = current.parent

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class UserStudyInfo(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="study_info",
    )
    faculty = models.CharField("Факультет", choices=FACULTY, max_length=20)
    student_group = models.CharField("Номер группы", max_length=50)
    study_form = models.CharField(
        "Форма обучения",
        choices=STUDY_FORM,
        default="Full-time",
        max_length=20,
    )

    class Meta:
        verbose_name = "Данные по учебе"
        verbose_name_plural = "Данные по учебе"

    def __str__(self):
        return f"{self.user} - {self.get_faculty_display()}, {self.student_group}"


class Passport(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="passport",
        verbose_name="Пользователь",
    )
    series = models.CharField(
        "Серия",
        max_length=4,
        help_text="4 цифры, например: 1234",
    )
    number = models.CharField(
        "Номер",
        max_length=6,
        help_text="6 цифр, например: 567890",
    )
    issued_by = models.CharField(
        "Кем выдан",
        max_length=255,
        help_text="Наименование органа, выдавшего паспорт",
    )
    date_of_issue = models.DateField("Дата выдачи")
    unit_code = models.CharField(
        "Код подразделения",
        max_length=7,
        help_text="Формат 123-456 или 123456",
    )
    registration_address = models.TextField("Адрес регистрации")

    class Meta:
        verbose_name = "Паспорт"
        verbose_name_plural = "Паспорта"

    def __str__(self):
        return f"Паспорт: {self.user}"

    def clean(self):
        super().clean()

        if self.series and not re.fullmatch(r"\d{4}", self.series):
            raise ValidationError({"series": "Серия паспорта должна содержать 4 цифры."})

        if self.number and not re.fullmatch(r"\d{6}", self.number):
            raise ValidationError({"number": "Номер паспорта должен содержать 6 цифр."})

        if self.unit_code and not re.fullmatch(r"\d{3}-?\d{3}", self.unit_code):
            raise ValidationError(
                {"unit_code": "Код подразделения должен быть в формате 123-456 или 123456."}
            )

        if self.date_of_issue:
            if self.date_of_issue > timezone.now().date():
                raise ValidationError(
                    {"date_of_issue": "Дата выдачи паспорта не может быть в будущем."}
                )

            birth_date = getattr(self.user, "birth_day", None)
            if birth_date:
                fourteen_years_later = birth_date.replace(year=birth_date.year + 14)
                if self.date_of_issue < fourteen_years_later:
                    raise ValidationError(
                        {
                            "date_of_issue": (
                                "Паспорт может быть выдан не ранее достижения 14 лет."
                            )
                        }
                    )

    def save(self, *args, **kwargs):
        if self.unit_code:
            self.unit_code = self.unit_code.replace("-", "")
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def full_number(self):
        return f"{self.series} {self.number}"