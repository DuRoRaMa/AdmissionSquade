from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, MembershipFee, SquadMembership, Role

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

from django.contrib import admin
from .models import SquadMembership



class MembershipFeeInline(admin.TabularInline):
    model = MembershipFee
    extra = 0  # сколько пустых форм показывать
    fields = ('amount', 'paid_at', 'expires_at')
    readonly_fields = ('paid_at',)

@admin.register(SquadMembership)
class SquadMembershipAdmin(admin.ModelAdmin):
    inlines = [MembershipFeeInline]
    list_display = ('id', 'user', 'squad', 'role', 'joined_date', 'is_active')
    list_filter = ('is_active', 'role', 'squad')
    search_fields = ('user__email', 'user__username', 'squad__name')
    raw_id_fields = ('user', 'squad')  # для больших списков удобно выбирать по id
    date_hierarchy = 'joined_date'

@admin.register(MembershipFee)
class MembershipFeeAdmin(admin.ModelAdmin):
    list_display = ('id', 'membership', 'amount', 'paid_at', 'expires_at')
    list_filter = ('paid_at', 'expires_at')
    search_fields = ('membership__user__email', 'membership__squad__name')
    raw_id_fields = ('membership',)
    date_hierarchy = 'paid_at'

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