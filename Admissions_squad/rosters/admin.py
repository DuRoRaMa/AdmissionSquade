from django.contrib import admin
from .models import (
    WorkBlock,
    AvailabilityForm,
    AvailabilityFormDay,
    AvailabilityFormShift,
    AvailabilitySlot,
    Schedule,
    ScheduleNeed,
    ScheduleEntry,
    ScheduleChangeRequest,
    ScheduleRecord,
    QrToken,
)


class AvailabilityFormShiftInline(admin.TabularInline):
    model = AvailabilityFormShift
    extra = 0


class AvailabilityFormDayInline(admin.StackedInline):
    model = AvailabilityFormDay
    extra = 0


@admin.register(WorkBlock)
class WorkBlockAdmin(admin.ModelAdmin):
    list_display = ('id', 'squad', 'code', 'name', 'is_active')
    list_filter = ('squad', 'is_active')
    search_fields = ('code', 'name')


@admin.register(AvailabilityForm)
class AvailabilityFormAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'squad', 'period_start', 'period_end', 'status', 'created_at')
    list_filter = ('squad', 'status')
    search_fields = ('title',)


@admin.register(AvailabilityFormDay)
class AvailabilityFormDayAdmin(admin.ModelAdmin):
    list_display = ('id', 'form', 'date')
    list_filter = ('form',)


@admin.register(AvailabilityFormShift)
class AvailabilityFormShiftAdmin(admin.ModelAdmin):
    list_display = ('id', 'day', 'shift_kind', 'title', 'starts_at', 'ends_at', 'is_active')
    list_filter = ('shift_kind', 'is_active')


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ('id', 'shift', 'membership', 'is_available', 'submitted_at')
    list_filter = ('is_available',)


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'squad', 'period_start', 'period_end', 'status', 'published_at')
    list_filter = ('status', 'squad')


@admin.register(ScheduleNeed)
class ScheduleNeedAdmin(admin.ModelAdmin):
    list_display = ('id', 'schedule', 'date', 'work_block', 'starts_at', 'ends_at', 'required_people')
    list_filter = ('schedule', 'work_block')


@admin.register(ScheduleEntry)
class ScheduleEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'schedule', 'membership', 'work_block', 'date', 'starts_at', 'ends_at', 'status')
    list_filter = ('schedule', 'work_block', 'status')


@admin.register(ScheduleChangeRequest)
class ScheduleChangeRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'entry', 'requested_by', 'request_type', 'status', 'created_at')
    list_filter = ('status', 'request_type')


@admin.register(ScheduleRecord)
class ScheduleRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'entry', 'checked_in_at', 'checked_out_at')


@admin.register(QrToken)
class QrTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'entry', 'expires_at', 'is_used', 'created_at')
    list_filter = ('is_used',)