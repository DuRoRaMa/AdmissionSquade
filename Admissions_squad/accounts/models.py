from __future__ import annotations

import re

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField

SYSTEM_ADMIN_ROLE_SLUG = "administrator"
BASE_USER_ROLE_SLUG = "base_user"
DEFAULT_MEMBER_ROLE_SLUG = "member"

SYSTEM_ADMIN_ROLE_CONFIG = {
    "name": "Администратор",
    "slug": SYSTEM_ADMIN_ROLE_SLUG,
    "description": "Системная родительская роль администратора.",
    "permissions": [],  # полный системный доступ всё равно остаётся через is_staff
    "is_system": True,
}

BASE_USER_ROLE_CONFIG = {
    "name": "Стандартная роль пользователя",
    "slug": BASE_USER_ROLE_SLUG,
    "description": "Базовая системная роль авторизованного пользователя.",
    "permissions": [
        "squad.view",
        "membership.join_own",
    ],
    "is_system": True,
}

DEFAULT_MEMBER_ROLE_CONFIG = {
    "name": "Участник",
    "slug": DEFAULT_MEMBER_ROLE_SLUG,
    "description": "Базовая роль участника отряда.",
    "permissions": [
        "fee.view_own",
        "availability.respond_own",
        "roster.view_own",
    ],
    "is_system": True,
    "parent_slug": BASE_USER_ROLE_SLUG,
}

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
                "description": "Просмотр карточек и данных отрядов.",
            },
            {
                "code": "squad.manage",
                "name": "Управление отрядом",
                "description": "Редактирование и управление отрядом.",
            },
        ],
    },
    {
        "key": "memberships",
        "title": "Участники",
        "permissions": [
            {
                "code": "membership.join_own",
                "name": "Вступление в отряд",
                "description": "Самостоятельное вступление пользователя в отряд.",
            },
            {
                "code": "membership.manage",
                "name": "Управление участниками",
                "description": "Добавление, изменение и исключение участников.",
            },
        ],
    },
    {
        "key": "fees",
        "title": "Взносы",
        "permissions": [
            {
                "code": "fee.view_own",
                "name": "Просмотр своих взносов",
                "description": "Просмотр собственных взносов участника.",
            },
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
                "code": "availability.respond_own",
                "name": "Заполнение своей доступности",
                "description": "Отправка своей формы доступности.",
            },
            {
                "code": "availability.manage",
                "name": "Управление доступностью",
                "description": "Создание и сопровождение форм доступности.",
            },
        ],
    },
    {
        "key": "rosters",
        "title": "Графики",
        "permissions": [
            {
                "code": "roster.view_own",
                "name": "Просмотр своего графика",
                "description": "Просмотр только своих смен.",
            },
            {
                "code": "roster.view_all",
                "name": "Просмотр общего графика",
                "description": "Просмотр общего графика отряда.",
            },
            {
                "code": "roster.manage",
                "name": "Управление графиками",
                "description": "Создание и редактирование графиков.",
            },
            {
                "code": "roster.publish",
                "name": "Публикация графиков",
                "description": "Публикация итогового графика.",
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
    
    @classmethod
    def _sync_role_from_config(cls, config: dict, parent=None):
        defaults = {
            "name": config["name"],
            "description": config["description"],
            "permissions": sorted(set(config.get("permissions") or [])),
            "is_system": config.get("is_system", False),
            "parent": parent,
        }

        role, _ = cls.objects.get_or_create(
            slug=config["slug"],
            defaults=defaults,
        )

        changed = False

        if role.name != config["name"]:
            role.name = config["name"]
            changed = True

        if role.description != config["description"]:
            role.description = config["description"]
            changed = True

        normalized_permissions = sorted(set(config.get("permissions") or []))
        if sorted(set(role.permissions or [])) != normalized_permissions:
            role.permissions = normalized_permissions
            changed = True

        if role.is_system is not config.get("is_system", False):
            role.is_system = config.get("is_system", False)
            changed = True

        if role.parent_id != (parent.id if parent else None):
            role.parent = parent
            changed = True

        if changed:
            role.save()

        return role

    @classmethod
    def ensure_system_roles(cls):
        admin_config = {
            **SYSTEM_ADMIN_ROLE_CONFIG,
            "permissions": sorted(ROLE_PERMISSION_CODES),
        }

        admin_role = cls._sync_role_from_config(admin_config)
        base_user_role = cls._sync_role_from_config(BASE_USER_ROLE_CONFIG)
        return {
            "administrator": admin_role,
            "base_user": base_user_role,
        }

    @classmethod
    def get_or_create_base_user_role(cls):
        return cls.ensure_system_roles()["base_user"]

    @classmethod
    def get_or_create_administrator_role(cls):
        return cls.ensure_system_roles()["administrator"]
    
    @classmethod
    def get_or_create_default_member_role(cls):
        system_roles = cls.ensure_system_roles()
        parent_role = system_roles["base_user"]

        defaults = {
            "name": DEFAULT_MEMBER_ROLE_CONFIG["name"],
            "description": DEFAULT_MEMBER_ROLE_CONFIG["description"],
            "permissions": DEFAULT_MEMBER_ROLE_CONFIG["permissions"],
            "is_system": DEFAULT_MEMBER_ROLE_CONFIG["is_system"],
            "parent": parent_role,
        }

        role, _ = cls.objects.get_or_create(
            slug=DEFAULT_MEMBER_ROLE_CONFIG["slug"],
            defaults=defaults,
        )

        changed = False

        if role.name != DEFAULT_MEMBER_ROLE_CONFIG["name"]:
            role.name = DEFAULT_MEMBER_ROLE_CONFIG["name"]
            changed = True

        if role.description != DEFAULT_MEMBER_ROLE_CONFIG["description"]:
            role.description = DEFAULT_MEMBER_ROLE_CONFIG["description"]
            changed = True

        normalized_permissions = sorted(set(DEFAULT_MEMBER_ROLE_CONFIG["permissions"]))
        if sorted(set(role.permissions or [])) != normalized_permissions:
            role.permissions = normalized_permissions
            changed = True

        if role.is_system is not True:
            role.is_system = True
            changed = True

        if role.parent_id != parent_role.id:
            role.parent = parent_role
            changed = True

        if changed:
            role.save()

        return role
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