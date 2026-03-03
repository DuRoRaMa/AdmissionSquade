from django.db import models
from accounts.models import CustomUser, Role
# Create your models here.

class Squad(models.Model):
    name = models.CharField('Название отряда', max_length=150, unique=True)
    description = models.TextField('Описание отряда', blank=True)
    #regional_office = 
    #region = 
    #employer
    #LSO_directions = 
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta():
        verbose_name = "Отряд"
        verbose_name_plural = "Отряды"

    def __str__(self):
        return self.name

class SquadMembership(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='membersips')
    squad = models.ForeignKey(Squad, on_delete=models.CASCADE, related_name='memberships')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    #gender
    #birth_day
    #snils
    #inn
    #ticket_number
    #university
    #faculty
    #student_group
    #study_form
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
