from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Добавляем наши поля в стандартные fieldsets
    fieldsets = UserAdmin.fieldsets + (
        ("Дополнительная информация", {"fields": ("middle_name", "phone")}),
    )
    
    # Добавляем поля при создании пользователя
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Дополнительная информация", {"fields": ("last_name", "first_name","middle_name", "phone", "email")}),
    )
    
    list_display = ("username", "email", "get_full_name", "phone", "is_staff")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "first_name", "last_name", "middle_name", "email", "phone")
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = "ФИО"