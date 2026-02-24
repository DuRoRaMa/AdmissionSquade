from django.db import models

# Create your models here.

class Squad(models.Model):
    name = models.CharField('Название отряда', max_length=150, unique=True)
    description = models.TextField('Описание отряда', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta():
        verbose_name = "Отряд"
        verbose_name_plural = "Отряды"

    def __str__(self):
        return self.name