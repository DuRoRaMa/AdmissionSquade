from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import Squad, SquadMembership, MembershipFee

class SquadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Squad
        fields = ('name', 'regional_office', 'region', 'employer')

class MembershipFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipFee
        fields = ('amount', 'paid_at', 'expires_at')

class SquadMembershipSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    squad = SquadSerializer(read_only=True)
    fees =  MembershipFeeSerializer(many=True, read_only=True)
    class Meta:
        model = SquadMembership
        fields = ('role', 'squad', 'university', 'joined_date', 'is_active', 'fees')
    
    def get_role(self, obj):
        from accounts.serializers import RoleSerializer  # отложенный импорт
        if obj.role:
            return RoleSerializer(obj.role).data
        return None