from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import CustomUser, Role 
from squads.models import Squad, SquadMembership, MembershipFee
import re

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        validators=[validate_password]
    )
    conf_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        label='Подтверждение пароля'
    )
    
    class Meta:
        model = CustomUser
        fields = (
            'username',
            'email',
            'first_name',
            'last_name',
            'middle_name',
            'password',
            'conf_password',
        )
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True}
        }

    def validate_email(self, value):
        value = value.lower().strip()
        dvfu_email_regex = r'^[a-zA-z0-9]+@(?:dvfu\.ru|students\.dvfu\.ru)$'
        if not re.match(dvfu_email_regex, value):
            raise serializers.ValidationError(
                'Разрешены только email адреса ДВФУ: name@dvfu.ru или name@students.dvfu.ru'
            )
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError('пользователь с таким email уже существует')
        return value

    def validate(self, data):
        if data['password'] != data['conf_password']:
            raise serializers.ValidationError({'conf_password': 'Пароли не совпадают.'})
        return data
    
    def create(self, validated_data):
        validated_data.pop('conf_password')
        password = validated_data.pop('password')

        user = CustomUser.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class SquadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Squad
        fields = ('name',)
class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ('name',)

class MembershipFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipFee
        fields = ('amount', 'paid_at', 'expires_at')

class SquadMembershipSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    squad = SquadSerializer(read_only=True)
    fees =  MembershipFeeSerializer(many=True, read_only=True)
    class Meta:
        model = SquadMembership
        fields = ('role', 'squad', 'joined_date', 'is_active', 'fees')

class ProfileUserSerializer(serializers.ModelSerializer):
    memberships = SquadMembershipSerializer(many=True, read_only=True, source='membersips')
    class Meta:
        model = CustomUser
        fields = (
            'email',
            'username',
            'first_name',
            'last_name',
            'middle_name',
            'phone',
            'is_blocked',
            'created_at',
            'updated_at',
            'memberships',
            )
        read_only_fields = (
            'email',
            'username',
            'is_blocked',
            'created_at',
            'updated_at',
            'memberships',
        )
        
        def validate_phone(self, value):
            if value:
                request = self.context.get('request')
                if request and request.user.is_authenticated:
                    if CustomUser.objects.filter(phone=value).exclude(pk=request.user.pk).exists():
                        raise serializers.ValidationError('Этот номер телефона уже используется')
            return value
        
        def update(self, instance, validated_data):
            instance.first_name = validated_data.get('first_name', instance.first_name)
            instance.last_name = validated_data.get('last_name', instance.last_name)
            instance.middle_name = validated_data.get('middle_name', instance.middle_name)
            instance.phone = validated_data.get('phone', instance.phone)
            try:
                instance.full_clean()
            except DjangoValidationError as e:
                raise serializers.ValidationError(e.message_dict)
            instance.save()
            return instance