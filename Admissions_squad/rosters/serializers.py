from rest_framework import serializers

from accounts.permissions import user_has_role_permission
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
    AttendanceActionLog
)
from rosters.services.attendance_status import (
    get_entry_attendance_status,
    get_entry_record,
)

class WorkBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkBlock
        fields = "__all__"


class AvailabilityFormShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityFormShift
        fields = ("id", "shift_kind", "title", "starts_at", "ends_at", "is_active")


class AvailabilityFormDaySerializer(serializers.ModelSerializer):
    shifts = AvailabilityFormShiftSerializer(many=True)

    class Meta:
        model = AvailabilityFormDay
        fields = ("id", "date", "shifts")


class AvailabilityFormSerializer(serializers.ModelSerializer):
    days = AvailabilityFormDaySerializer(many=True)
    squad_name = serializers.CharField(source='squad.name', read_only=True)
    work_blocks = serializers.SerializerMethodField()
    class Meta:
        model = AvailabilityForm
        fields = (
            "id",
            "squad",
            "squad_name",
            "title",
            "period_start",
            "period_end",
            "response_deadline",
            "allow_work_block_choice",
            "work_blocks",
            "status",
            "created_by",
            "created_at",
            "days",
        )
        read_only_fields = ("created_by", "created_at", "status")

    def get_work_blocks(self, obj):
            if not obj.allow_work_block_choice:
                return []

            blocks = WorkBlock.objects.filter(
                squad=obj.squad,
                is_active=True,
            ).order_by("name")

            return WorkBlockSerializer(blocks, many=True).data

    def validate(self, attrs):
        period_start = attrs.get("period_start")
        period_end = attrs.get("period_end")
        days = attrs.get("days", [])

        if period_start and period_end and period_end < period_start:
            raise serializers.ValidationError(
                "Дата окончания периода не может быть раньше даты начала."
            )

        for day in days:
            day_date = day.get("date")
            if period_start and period_end and day_date and not (period_start <= day_date <= period_end):
                raise serializers.ValidationError(
                    f"Дата {day_date} выходит за пределы периода формы доступности."
                )

        return attrs

    def create(self, validated_data):
        days_data = validated_data.pop("days", [])
        form = AvailabilityForm.objects.create(**validated_data)

        for day_data in days_data:
            shifts_data = day_data.pop("shifts", [])
            day = AvailabilityFormDay.objects.create(form=form, **day_data)

            for shift_data in shifts_data:
                AvailabilityFormShift.objects.create(day=day, **shift_data)

        return form


class AvailabilitySlotInputSerializer(serializers.Serializer):
    shift_id = serializers.IntegerField()
    is_available = serializers.BooleanField()
    preferred_work_block = serializers.IntegerField(
        required=False,
        allow_null=True
    )
    comment = serializers.CharField(required=False, allow_blank=True)


class AvailabilitySubmitSerializer(serializers.Serializer):
    slots = AvailabilitySlotInputSerializer(many=True)

    def validate_slots(self, value):
        shift_ids = [item["shift_id"] for item in value]
        if len(shift_ids) != len(set(shift_ids)):
            raise serializers.ValidationError(
                "Нельзя передавать одну и ту же смену несколько раз."
            )
        return value


class AvailabilitySlotSerializer(serializers.ModelSerializer):
    shift = AvailabilityFormShiftSerializer()
    preferred_work_block = WorkBlockSerializer(read_only=True)
    class Meta:
        model = AvailabilitySlot
        fields = ("id", "shift", "is_available", "preferred_work_block", "comment", "submitted_at")


class ScheduleNeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleNeed
        fields = (
            "id",
            "schedule",
            "date",
            "work_block",
            "starts_at",
            "ends_at",
            "required_people",
        )
        read_only_fields = ("id", "schedule")


class ScheduleSerializer(serializers.ModelSerializer):
    needs = ScheduleNeedSerializer(many=True, required=False)
    has_entries = serializers.SerializerMethodField()
    entries_count = serializers.SerializerMethodField()
    availability_form_title = serializers.CharField(
        source='availability_form.title',
        read_only=True,
    )
    class Meta:
        model = Schedule
        fields = (
            "id",
            "squad",
            "availability_form",
            "availability_form_title",
            "title",
            "period_start",
            "period_end",
            "status",
            "published_at",
            "created_by",
            "created_at",
            "needs",
            "has_entries",
            "entries_count"
        )
        read_only_fields = ("created_by", "created_at", "published_at", "status","availability_form_title", "period_start", "period_end", "has_entries", "entries_count")

    def get_has_entries(self, obj):
        if hasattr(obj, "entries_count_value"):
            return obj.entries_count_value > 0
        return obj.entries.exists()
    
    def get_entries_count(self, obj):
        if hasattr(obj, "entries_count_value"):
            return obj.entries_count_value

        return obj.entries.count()
    
    def validate(self, attrs):
        request = self.context.get("request")
        instance = getattr(self, "instance", None)

        squad = attrs.get("squad") or getattr(instance, "squad", None)
        availability_form = (
            attrs.get("availability_form")
            or getattr(instance, "availability_form", None)
        )
        needs = attrs.get("needs", [])

        if not availability_form:
            raise serializers.ValidationError({
                "availability_form": "Выберите форму доступности для графика."
            })

        if availability_form.status != "closed":
            raise serializers.ValidationError({
                "availability_form": "График можно создать только по закрытой форме доступности."
            })

        if squad and availability_form.squad_id != squad.id:
            raise serializers.ValidationError({
                "availability_form": "Форма доступности должна относиться к выбранному отряду."
            })

        for need in needs:
            need_date = need.get("date")

            if (
                need_date
                and not (
                    availability_form.period_start
                    <= need_date
                    <= availability_form.period_end
                )
            ):
                raise serializers.ValidationError(
                    f"Потребность на дату {need_date} выходит за пределы периода формы доступности."
                )

            work_block = need.get("work_block")

            if work_block and squad and work_block.squad_id != squad.id:
                raise serializers.ValidationError({
                    "work_block": "Блок потребности должен относиться к выбранному отряду."
                })

        return attrs

    def create(self, validated_data):
        needs_data = validated_data.pop("needs", [])
        availability_form = validated_data["availability_form"]
        schedule = Schedule.objects.create(
            **validated_data,
            period_start=availability_form.period_start,
            period_end=availability_form.period_end
        )

        for need_data in needs_data:
            ScheduleNeed.objects.create(schedule=schedule, **need_data)

        return schedule

class AttendanceFieldsMixin(serializers.Serializer):
    checked_in_at = serializers.SerializerMethodField()
    checked_out_at = serializers.SerializerMethodField()
    attendance_status = serializers.SerializerMethodField()
    attendance_status_label = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()

    def _get_record(self, obj):
        try:
            return obj.record
        except ScheduleRecord.DoesNotExist:
            return None

    def get_checked_in_at(self, obj):
        record = self._get_record(obj)
        return record.checked_in_at if record else None

    def get_checked_out_at(self, obj):
        record = self._get_record(obj)
        return record.checked_out_at if record else None

    def get_attendance_status(self, obj):
        record = self._get_record(obj)
        return get_entry_attendance_status(obj, record)

    def get_attendance_status_label(self, obj):
        status = self.get_attendance_status(obj)
        labels = dict(ScheduleEntry.STATUS_CHOICES)
        return labels.get(status, status)

    def get_status_label(self, obj):
        status = getattr(obj, "status", None)
        labels = dict(ScheduleEntry.STATUS_CHOICES)
        return labels.get(status, status)

class ScheduleEntrySerializer(AttendanceFieldsMixin, serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    work_block_name = serializers.CharField(source="work_block.name", read_only=True)
    work_block_code = serializers.CharField(source="work_block.code", read_only=True)

    class Meta:
        model = ScheduleEntry
        fields = (
            "id",
            "schedule",
            "need",
            "membership",
            "member_name",
            "work_block",
            "work_block_name",
            "work_block_code",
            "date",
            "starts_at",
            "ends_at",
            "status",
            "checked_in_at",
            "checked_out_at",
            "attendance_status",
            "attendance_status_label",
        )

    def get_member_name(self, obj):
        user = obj.membership.user if obj.membership else None
        if not user:
            return ""
        return f"{user.last_name} {user.first_name} {user.middle_name}".strip()


class ScheduleChangeRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleChangeRequest
        fields = "__all__"
        read_only_fields = ("requested_by", "status", "reviewed_by", "reviewed_at", "created_at")

    def validate(self, attrs):
        request = self.context.get("request")
        entry = attrs.get("entry")
        target_membership = attrs.get("target_membership")
        request_type = attrs.get("request_type")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Не удалось определить пользователя запроса.")

        if entry.membership.user_id != request.user.id and not request.user.is_staff:
            raise serializers.ValidationError("Можно создавать заявку только по своей смене.")

        squad = entry.schedule.squad
        if not request.user.is_staff and not user_has_role_permission(
            request.user,
            "roster.view_own",
            squad=squad,
        ):
            raise serializers.ValidationError("Недостаточно прав для работы со своей сменой.")

        if request_type == "swap":
            if not target_membership:
                raise serializers.ValidationError(
                    {"target_membership": "Для swap нужно указать заменяющего."}
                )

            if target_membership.squad_id != entry.membership.squad_id:
                raise serializers.ValidationError(
                    {"target_membership": "Заменяющий должен быть из того же отряда."}
                )

            if not target_membership.is_active:
                raise serializers.ValidationError(
                    {"target_membership": "Нельзя выбрать неактивное членство."}
                )

        if entry.schedule.status != "published":
            raise serializers.ValidationError(
                "Заявку можно создать только по опубликованному графику."
            )

        return attrs


class ScheduleRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleRecord
        fields = "__all__"


class QrTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = QrToken
        fields = ("id", "entry", "token", "expires_at", "is_used", "created_at")
        read_only_fields = ("token", "expires_at", "is_used", "created_at")

class AvailabilityResponseItemSerializer(serializers.Serializer):
    shift_id = serializers.IntegerField()
    date = serializers.DateField()
    shift_title = serializers.CharField()
    starts_at = serializers.TimeField()
    ends_at = serializers.TimeField()
    is_available = serializers.BooleanField()
    comment = serializers.CharField(allow_blank=True, required=False)
    submitted_at = serializers.DateTimeField(allow_null=True)


class AvailabilityResponseMemberSerializer(serializers.Serializer):
    membership_id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    full_name = serializers.CharField()
    role_name = serializers.CharField(allow_blank=True, required=False)
    has_response = serializers.BooleanField()
    available_count = serializers.IntegerField()
    unavailable_count = serializers.IntegerField()
    submitted_at = serializers.DateTimeField(allow_null=True)
    slots = AvailabilityResponseItemSerializer(many=True)

class AttendanceActionLogSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    member_name = serializers.SerializerMethodField()
    scanner_name = serializers.SerializerMethodField()
    work_block_name = serializers.CharField(source="entry.work_block.name", read_only=True)
    entry_date = serializers.DateField(source="entry.date", read_only=True)
    starts_at = serializers.TimeField(source="entry.starts_at", read_only=True)
    ends_at = serializers.TimeField(source="entry.ends_at", read_only=True)

    class Meta:
        model = AttendanceActionLog
        fields = (
            "id",
            "entry",
            "entry_date",
            "starts_at",
            "ends_at",
            "work_block_name",
            "action",
            "action_label",
            "member_name",
            "scanner_name",
            "created_at",
        )

    def get_member_name(self, obj):
        user = obj.entry.membership.user if obj.entry and obj.entry.membership else None

        if not user:
            return ""

        return f"{user.last_name} {user.first_name} {user.middle_name}".strip() or user.email

    def get_scanner_name(self, obj):
        user = obj.scanned_by

        if not user:
            return ""

        return f"{user.last_name} {user.first_name} {user.middle_name}".strip() or user.email

class AttendanceEntrySerializer(AttendanceFieldsMixin, serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    work_block_name = serializers.CharField(source="work_block.name", read_only=True)
    checked_in_at = serializers.SerializerMethodField()
    checked_out_at = serializers.SerializerMethodField()
    can_manual_check_in = serializers.SerializerMethodField()
    can_manual_check_out = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleEntry
        fields = [
            "id",
            "date",
            "starts_at",
            "ends_at",
            "full_name",
            "work_block_name",
            "checked_in_at",
            "checked_out_at",
            "can_manual_check_in",
            "can_manual_check_out",
        ]

    def _get_record(self, obj):
        try:
            return obj.record
        except ScheduleRecord.DoesNotExist:
            return None

    def get_full_name(self, obj):
        user = obj.membership.user
        return user.get_full_name() or user.email

    def get_checked_in_at(self, obj):
        record = self._get_record(obj)
        return record.checked_in_at if record else None

    def get_checked_out_at(self, obj):
        record = self._get_record(obj)
        return record.checked_out_at if record else None

    def get_can_manual_check_in(self, obj):
        record = self._get_record(obj)
        return not record or not record.checked_in_at

    def get_can_manual_check_out(self, obj):
        record = self._get_record(obj)
        return bool(record and record.checked_in_at and not record.checked_out_at)
