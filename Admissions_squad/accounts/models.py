from django.db import models
from django.contrib.auth.models import AbstractUser
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError
import re

class CustomUser(AbstractUser):
    email = models.EmailField('Email', unique=True, error_messages={'unique': 'Пользователь с таким Email уже существует.'})
    username = models.CharField('Имя пользователя', max_length=150, unique=True, help_text='Обязательное поле. Не более 150 символов.')
    middle_name = models.CharField("Отчество", max_length=150, blank=True)
    phone = PhoneNumberField('Номер телефона', unique=True, max_length=30, blank=True, null=True, region='RU', help_text="Формат: +7XXXXXXXXXX", error_messages={'unique': 'Этот номер телефона уже используется.'})
    is_blocked = models.BooleanField('Заблокирован', default=False)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'username']
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
        super().save(*args, **kwargs)

class Role(models.Model):
    name = models.CharField('Роль пользователя', max_length=50, unique=True)
    class Meta():
        verbose_name = "Роль в отряде"
        verbose_name_plural = "Роли в отрядах"
    def __str__(self):
        return self.name
class SquadMembership(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='membersips')
    squad = models.ForeignKey('squads.Squad', on_delete=models.CASCADE, related_name='memberships')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    joined_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta():
        verbose_name = "Членство в отряде"
        verbose_name_plural = "Челенства в отрядах"

class MembershipFee(models.Model):
    membership = models.ForeignKey(SquadMembership, on_delete=models.CASCADE, related_name='fees')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    class Meta():
        verbose_name = "Членский взнос"
        verbose_name_plural = "Челенские взносы"