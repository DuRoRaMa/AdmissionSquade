from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from accounts.models import CustomUser
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from notifications.services import EmailCodeError, verify_registration_code
import re
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        email = attrs.get("email", "").lower().strip()
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError({
                "detail": "Неверный email или пароль."
            })
        if not user.is_active:
            raise serializers.ValidationError({
                "detail": "Учетная запись деактивирована."
            })
        if user.is_blocked:
            raise serializers.ValidationError({
                "detail": "Учетная запись заблокирована."
            })
        return super().validate(attrs)

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

    email_code = serializers.CharField(
        write_only=True,
        required=True,
        max_length=6,
        min_length=6,
        label='Код подтверждения email'
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
            'email_code',
        )
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True}
        }

    def validate_email(self, value):
        value = value.lower().strip()

        dvfu_email_regex = r'^[a-zA-Z0-9._%+-]+@(?:dvfu\.ru|students\.dvfu\.ru)$'

        if not re.match(dvfu_email_regex, value):
            raise serializers.ValidationError(
                'Разрешены только email адреса ДВФУ: name@dvfu.ru или name@students.dvfu.ru'
            )

        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError('Пользователь с таким email уже существует.')

        return value

    def validate(self, data):
        if data['password'] != data['conf_password']:
            raise serializers.ValidationError({
                'conf_password': 'Пароли не совпадают.'
            })

        try:
            verify_registration_code(
                email=data['email'],
                code=data['email_code']
            )
        except EmailCodeError as error:
            raise serializers.ValidationError({
                'email_code': str(error)
            })

        return data

    def create(self, validated_data):
        validated_data.pop('conf_password')
        validated_data.pop('email_code')

        password = validated_data.pop('password')

        user = CustomUser.objects.create_user(
            password=password,
            **validated_data
        )

        return user

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )

    conf_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )

    def validate(self, data):
        if data['password'] != data['conf_password']:
            raise serializers.ValidationError({
                'conf_password': 'Пароли не совпадают.'
            })

        try:
            user_id = force_str(urlsafe_base64_decode(data['uid']))
            user = CustomUser.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            raise serializers.ValidationError({
                'detail': 'Ссылка для восстановления пароля недействительна.'
            })

        if not default_token_generator.check_token(user, data['token']):
            raise serializers.ValidationError({
                'detail': 'Ссылка для восстановления пароля недействительна или устарела.'
            })

        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['password'])
        user.save(update_fields=['password'])
        return user
