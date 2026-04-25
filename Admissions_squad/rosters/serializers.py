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

    class Meta:
        model = AvailabilityForm
        fields = (
            "id",
            "squad",
            "title",
            "period_start",
            "period_end",
            "response_deadline",
            "status",
            "created_by",
            "created_at",
            "days",
        )
        read_only_fields = ("created_by", "created_at", "status")

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

    class Meta:
        model = AvailabilitySlot
        fields = ("id", "shift", "is_available", "comment", "submitted_at")


class ScheduleNeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleNeed
        fields = "__all__"


class ScheduleSerializer(serializers.ModelSerializer):
    needs = ScheduleNeedSerializer(many=True, required=False)

    class Meta:
        model = Schedule
        fields = (
            "id",
            "squad",
            "title",
            "period_start",
            "period_end",
            "status",
            "published_at",
            "created_by",
            "created_at",
            "needs",
        )
        read_only_fields = ("created_by", "created_at", "published_at", "status")

    def validate(self, attrs):
        period_start = attrs.get("period_start")
        period_end = attrs.get("period_end")
        needs = attrs.get("needs", [])

        if period_start and period_end and period_end < period_start:
            raise serializers.ValidationError(
                "Дата окончания периода графика не может быть раньше даты начала."
            )

        for need in needs:
            need_date = need.get("date")
            if period_start and period_end and need_date and not (period_start <= need_date <= period_end):
                raise serializers.ValidationError(
                    f"Потребность на дату {need_date} выходит за пределы периода графика."
                )

        return attrs

    def create(self, validated_data):
        needs_data = validated_data.pop("needs", [])
        schedule = Schedule.objects.create(**validated_data)

        for need_data in needs_data:
            ScheduleNeed.objects.create(schedule=schedule, **need_data)

        return schedule


class ScheduleEntrySerializer(serializers.ModelSerializer):
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