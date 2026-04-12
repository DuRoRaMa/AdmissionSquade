from django.db import models
from django.contrib.auth.models import AbstractUser
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError
from django.utils import timezone
import re

GENDER = [
    ('male', 'Мужской'),
    ('female', 'Женский'),
]

FACULTY = [
    ('IMKT','ИМКТ'),
    ('VI','ВИ'),
    ('PISH','ПИШ'),
    ('SHIGN','ШИГН'),
    ('IMO','ИМО'),
    ('PI','ПИ'),
    ('ITPM','ИТПМ'),
    ('SHMINZ','ШМИНЖ'),
    ('IFKS','ИФКС'),
    ('USH','ЮШ'),
    ('SHEM','ШЭМ'),
    ('SHP','ШП'),
]

STUDY_FORM = [
    ('Full-time', 'Очная'),
    ('Full-part-time', 'Очно-заочная'),
    ('Part-time', 'Заочная'),
]

class CustomUser(AbstractUser):
    email = models.EmailField('Email', unique=True, error_messages={'unique': 'Пользователь с таким Email уже существует.'})
    username = models.CharField('Имя пользователя', max_length=150, unique=True, help_text='Обязательное поле. Не более 150 символов.')
    middle_name = models.CharField("Отчество", max_length=150, blank=True)
    phone = PhoneNumberField('Номер телефона', unique=True, max_length=30, blank=True, null=True, region='RU', help_text="Формат: +7XXXXXXXXXX", error_messages={'unique': 'Этот номер телефона уже используется.'})
    is_blocked = models.BooleanField('Заблокирован', default=False)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    gender = models.CharField('Пол', choices=GENDER, blank=True, null=True)
    birth_day = models.DateField('День рождения', default='2000-01-01')   
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'username']

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        db_table = 'users'
        ordering = ['-date_joined']

    def __str__(self):
        name = self.get_full_name()
        return f'{self.email} ({name if name else self.username})'

    def get_full_name(self):
        parts = [self.last_name, self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        return ' '.join(parts)

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.lower().strip()
            # исправлено регулярное выражение: теперь допускает точки и дефисы в локальной части
            dvfu_email_regex = r'^[a-zA-Z0-9._%+-]+@(?:dvfu\.ru|students\.dvfu\.ru)$'
            if not re.match(dvfu_email_regex, self.email):
                raise ValidationError({
                    'email': (
                        'Разрешены только email адреса ДВФУ: '
                        'name@dvfu.ru или name@students.dvfu.ru'
                    )
                })

    # 14: save() больше не дублирует нормализацию; можно вызвать full_clean() для гарантии,
    # но осторожно – может привести к рекурсии при сохранении из админки.
    # Рекомендуется оставить только clean(), а в save() явно не вызывать full_clean()
    # (это делает сам Django при валидации модели). Поэтому save() переопределять не обязательно,
    # но если нужна дополнительная логика – оставляем без вызова clean() повторно.
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)



class Role(models.Model):
    name = models.CharField('Роль пользователя', max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    class Meta:
        verbose_name = "Роль в отряде"
        verbose_name_plural = "Роли в отрядах"

    def __str__(self):
        return self.name


class UserStudyInfo(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='study_info')
    faculty = models.CharField('Факультет', choices=FACULTY)
    student_group = models.CharField('Номер группы', max_length=50)
    study_form = models.CharField('Форма обучения', choices=STUDY_FORM, default='Full-time')

    class Meta:
        verbose_name = "Данные по учебе"
        verbose_name_plural = "Данные по учебе"
        unique_together = ('user',)

    def __str__(self):
        return f"{self.user} - {self.get_faculty_display()}, {self.student_group}"
class Passport(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='passport',
        verbose_name='Пользователь'
    )
    series = models.CharField(
        'Серия',
        max_length=4,
        help_text='4 цифры, например: 1234'
    )
    number = models.CharField(
        'Номер',
        max_length=6,
        help_text='6 цифр, например: 567890'
    )
    issued_by = models.CharField(
        'Кем выдан',
        max_length=255,
        help_text='Наименование органа, выдавшего паспорт'
    )
    date_of_issue = models.DateField('Дата выдачи')
    unit_code = models.CharField(
        'Код подразделения',
        max_length=7,
        help_text='Формат: XXX-XXX или XXXXXX (6-7 символов)'
    )
    registration_address = models.TextField(
        'Адрес регистрации',
        help_text='Полный адрес по месту жительства',
        default='Кампус двфу'
    )
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Паспорт'
        verbose_name_plural = 'Паспорта'
        ordering = ['-created_at']

    def __str__(self):
        return f'Паспорт {self.series} {self.number} ({self.user.email})'

    def clean(self):
        """Валидация форматов серии, номера и кода подразделения."""
        from django.core.exceptions import ValidationError
        import re

        if not re.fullmatch(r'\d{4}', self.series):
            raise ValidationError({'series': 'Серия должна содержать ровно 4 цифры.'})

        if not re.fullmatch(r'\d{6}', self.number):
            raise ValidationError({'number': 'Номер должен содержать ровно 6 цифр.'})

        if not re.fullmatch(r'\d{6}|\d{3}-\d{3}', self.unit_code):
            raise ValidationError({'unit_code': 'Код подразделения должен быть в формате XXX-XXX или XXXXXX.'})

        if self.date_of_issue and self.date_of_issue > timezone.now().date():
            raise ValidationError({'date_of_issue': 'Дата выдачи не может быть в будущем.'})
        if self.user and self.user.birth_day:
            birth_date = self.user.birth_day
            issue_date = self.date_of_issue

            if issue_date < birth_date:
                raise ValidationError({
                    'date_of_issue': 'Дата выдачи паспорта не может быть раньше даты рождения.'
                })

            # Вычисляем дату, когда пользователю исполнилось 14 лет
            fourteen_years_later = birth_date.replace(year=birth_date.year + 14)
            if issue_date < fourteen_years_later:
                raise ValidationError({
                    'date_of_issue': 'Паспорт может быть выдан не ранее достижения 14 лет.'
                })
    def save(self, *args, **kwargs):
        if self.unit_code:
            self.unit_code = self.unit_code.replace('-', '')
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def full_number(self):
        """Возвращает серию и номер как одну строку (например, '1234 567890')."""
        return f'{self.series} {self.number}'