from rest_framework import serializers
from .models import Squad, SquadMembership, MembershipFee
from accounts.serializers import RoleSerializer, UserListSerializer


class SquadSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Squad
        fields = (
            'id', 'name', 'description', 'regional_office', 'region',
            'employer', 'lso_directions', 'created_at', 'member_count'
        )
        read_only_fields = ('id', 'created_at', 'member_count')

    def get_member_count(self, obj):
        return obj.memberships.filter(is_active=True).count()


class MembershipFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipFee
        fields = ('id', 'amount', 'paid_at', 'expires_at')
        read_only_fields = ('id',)

    def validate(self, data):
        if data['paid_at'] > data['expires_at']:
            raise serializers.ValidationError('Дата истечения не может быть раньше даты уплаты.')
        return data


class SquadMembershipSerializer(serializers.ModelSerializer):
    role_detail = RoleSerializer(source="role", read_only=True)
    squad_detail = SquadSerializer(source="squad", read_only=True)
    user_detail = serializers.SerializerMethodField()
    fees = MembershipFeeSerializer(many=True, read_only=True)

    class Meta:
        model = SquadMembership
        fields = (
            "id",
            "user",
            "user_detail",
            "squad",
            "squad_detail",
            "role",
            "role_detail",
            "ticket_number",
            "university",
            "joined_date",
            "is_active",
            "fees",
        )
        read_only_fields = (
            "id",
            "joined_date",
            "user_detail",
            "squad_detail",
            "role_detail",
            "fees",
        )
        extra_kwargs = {
            "user": {"required": False},
            "squad": {"required": False},
            "role": {"required": False},
        }

    def get_user_detail(self, obj):
        return UserListSerializer(obj.user).data if obj.user else None

    def validate(self, data):
        request = self.context.get("request")
        context_squad = self.context.get("squad")

        user = data.get("user") or getattr(request, "user", None)
        squad = data.get("squad") or context_squad

        if not self.instance:
            if not user or not getattr(user, "is_authenticated", False):
                raise serializers.ValidationError("Не удалось определить пользователя.")
            if not squad:
                raise serializers.ValidationError("Не удалось определить отряд.")

            if SquadMembership.objects.filter(user=user, squad=squad, is_active=True).exists():
                raise serializers.ValidationError("Пользователь уже состоит в этом отряде.")

            if SquadMembership.objects.filter(user=user, is_active=True).exclude(squad=squad).exists():
                raise serializers.ValidationError(
                    "Пользователь уже состоит в другом отряде. Сначала выйдите из текущего."
                )

        return data