from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from accounts.models import CustomUser
from django.contrib.auth.password_validation import validate_password
import re
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        data = super().validate(attrs)
        return data

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
