from django.contrib import admin
from .models import Squad, MembershipFee, SquadMembership
# Register your models here.

admin.site.register(Squad)
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