from django.db import models
from django.contrib.auth.models import AbstractUser
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError
import re

class CustomUser(AbstractUser):
    email = models.EmailField('Email', unique=True, error_messages={'unique': 'Пользователь с таким Email уже существует.'})
    username = models.CharField('Имя пользователя', max_length=150, unique=True, blank=True, null=True, help_text='Автоматически генерируется из email (часть до символа @)')
    middle_name = models.CharField("Отчество", max_length=150, blank=True)
    phone = PhoneNumberField('Номер телефона', unique=True, max_length=30, blank=True, null=True, region='RU', help_text="Формат: +7XXXXXXXXXX", error_messages={'unique': 'Этот номер телефона уже используется.'})
    is_blocked = models.BooleanField('Заблокирован', default=False)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name','last_name']
    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        db_table = 'users'
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.email} ({self.get_full_name()} or {self.username})'
    
    def get_full_name(self):
        parts = [self.last_name, self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        return ' '.join(parts)
    
    def clean(self):
        super().clean()

        if self.email:
            self.email = self.email.lower().strip()
            dvfu_email_regex = r'^[a-zA-z0-9]+@(?:dvfu\.ru|students\.dvfu\.ru)$'
            if not re.match(dvfu_email_regex, self.email):
                raise ValidationError({
                    'email': (
                        'Разрешены только email адреса ДВФУ: '
                        'name@dvfu.ru или name@students.dvfu.ru'
                    )
                })

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower().strip()

        if self.email and not self.username:
            username = self.email.split('@')[0]
            if len(username) > 150:
                username = username[:150]
            origin_username = username
            counter = 1
            while CustomUser.objects.filter(username=username).exclude(pk=self.pk).exists():
                username = f'{origin_username}_{counter}'
                counter += 1
            self.username = username
            super().save(*args, **kwargs)
