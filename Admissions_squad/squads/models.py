from django.db import models
from accounts.models import CustomUser, Role
# Create your models here.


class Squad(models.Model):
    name = models.CharField('Название отряда', max_length=150, unique=True)
    description = models.TextField('Описание отряда', blank=True)
    regional_office = models.CharField('Региональное отделение', default='Приморское РО')
    region = models.CharField('Регион', default='Приморский край')
    employer = models.CharField('Работодатель', default='ФГАОУ ВО "ДВФУ"')
    lso_directions = models.CharField('Направление ЛСО', default='Студенческие сервисные отряды')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta():
        verbose_name = "Отряд"
        verbose_name_plural = "Отряды"

    def __str__(self):
        return self.name

class SquadMembership(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, related_name='membersips', null=True)
    squad = models.ForeignKey(Squad, on_delete=models.CASCADE, related_name='memberships')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    ticket_number = models.CharField('Номер членского билета', blank=True, null=True)
    university = models.CharField('Место учёбы', default='ФГАОУ ВО "ДВФУ"')
    joined_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta():
        unique_together = ('user', 'squad')
        verbose_name = "Членство в отряде"
        verbose_name_plural = "Членства в отрядах"

class MembershipFee(models.Model):
    membership = models.ForeignKey(SquadMembership, on_delete=models.CASCADE, related_name='fees')
    amount = models.DecimalField('Стоимость взноса', max_digits=10, decimal_places=2)
    paid_at = models.DateField('Дата уплаты')
    expires_at = models.DateField('Дата истечения')
    class Meta():
        verbose_name = "Членский взнос"
        verbose_name_plural = "Членские взносы"
