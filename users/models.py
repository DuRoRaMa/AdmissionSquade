from django.db import models
from django.contrib.auth.models import AbstractUser
from phonenumber_field.modelfields import PhoneNumberField


class CustomUser(AbstractUser):

    middle_name = models.CharField("Отчество", max_length=50, blank=True)
    phone = PhoneNumberField('Номер телефона',
                                    max_length=30,
                                    blank=True,
                                    region='RU',
                                    help_text="Формат: +7XXXXXXXXXX")

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        db_table = 'users'

    def get_full_name(self):
        parts = [self.last_name, self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        return ' '.join(parts)