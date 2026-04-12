from rest_framework import serializers
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
from squads.models import SquadMembership


class WorkBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkBlock
        fields = '__all__'


class AvailabilityFormShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityFormShift
        fields = ('id', 'shift_kind', 'title', 'starts_at', 'ends_at', 'is_active')


class AvailabilityFormDaySerializer(serializers.ModelSerializer):
    shifts = AvailabilityFormShiftSerializer(many=True)

    class Meta:
        model = AvailabilityFormDay
        fields = ('id', 'date', 'shifts')


class AvailabilityFormSerializer(serializers.ModelSerializer):
    days = AvailabilityFormDaySerializer(many=True)

    class Meta:
        model = AvailabilityForm
        fields = (
            'id',
            'squad',
            'title',
            'period_start',
            'period_end',
            'response_deadline',
            'status',
            'created_by',
            'created_at',
            'days',
        )
        read_only_fields = ('created_by', 'created_at', 'status')

    def create(self, validated_data):
        days_data = validated_data.pop('days', [])
        form = AvailabilityForm.objects.create(**validated_data)

        for day_data in days_data:
            shifts_data = day_data.pop('shifts', [])
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


class AvailabilitySlotSerializer(serializers.ModelSerializer):
    shift = AvailabilityFormShiftSerializer()

    class Meta:
        model = AvailabilitySlot
        fields = ('id', 'shift', 'is_available', 'comment', 'submitted_at')


class ScheduleNeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleNeed
        fields = '__all__'


class ScheduleSerializer(serializers.ModelSerializer):
    needs = ScheduleNeedSerializer(many=True, required=False)

    class Meta:
        model = Schedule
        fields = (
            'id',
            'squad',
            'title',
            'period_start',
            'period_end',
            'status',
            'published_at',
            'created_by',
            'created_at',
            'needs',
        )
        read_only_fields = ('created_by', 'created_at', 'published_at', 'status')

    def create(self, validated_data):
        needs_data = validated_data.pop('needs', [])
        schedule = Schedule.objects.create(**validated_data)

        for need_data in needs_data:
            ScheduleNeed.objects.create(schedule=schedule, **need_data)

        return schedule


class ScheduleEntrySerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    work_block_name = serializers.CharField(source='work_block.name', read_only=True)
    work_block_code = serializers.CharField(source='work_block.code', read_only=True)

    class Meta:
        model = ScheduleEntry
        fields = (
            'id',
            'schedule',
            'need',
            'membership',
            'member_name',
            'work_block',
            'work_block_name',
            'work_block_code',
            'date',
            'starts_at',
            'ends_at',
            'status',
        )

    def get_member_name(self, obj):
        user = obj.membership.user if obj.membership else None
        if not user:
            return ''
        return f'{user.last_name} {user.first_name} {user.middle_name}'.strip()


class ScheduleChangeRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleChangeRequest
        fields = '__all__'
        read_only_fields = ('requested_by', 'status', 'reviewed_by', 'reviewed_at', 'created_at')


class ScheduleRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleRecord
        fields = '__all__'


class QrTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = QrToken
        fields = ('id', 'entry', 'token', 'expires_at', 'is_used', 'created_at')
        read_only_fields = ('token', 'expires_at', 'is_used', 'created_at')