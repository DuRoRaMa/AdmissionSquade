from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from accounts.models import CustomUser
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from notifications.services import EmailCodeError, verify_registration_code
import re
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import CustomUser


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    default_error_messages = {
        "no_active_account": "Неверный email или пароль.",
    }

    def validate(self, attrs):
        email = attrs.get("email", "").lower().strip()
        attrs["email"] = email

        user = CustomUser.objects.filter(
            email__iexact=email,
        ).first()

        # Не сообщаем, существует ли такой email.
        if user is None:
            raise AuthenticationFailed(
                detail="Неверный email или пароль.",
                code="no_active_account",
            )

        if not user.is_active:
            raise AuthenticationFailed(
                detail="Учетная запись деактивирована.",
                code="inactive_account",
            )

        if user.is_blocked:
            raise AuthenticationFailed(
                detail="Учетная запись заблокирована.",
                code="blocked_account",
            )

        # При неверном пароле SimpleJWT теперь возьмёт
        # русское сообщение из default_error_messages.
        return super().validate(attrs)

class RegistrationDataSerializer(serializers.ModelSerializer):
    """
    Проверяет регистрационные данные без создания пользователя.
    Используется перед отправкой кода подтверждения.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        validators=[validate_password],
    )
    conf_password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        label="Подтверждение пароля",
    )

    class Meta:
        model = CustomUser
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "password",
            "conf_password",
        )
        extra_kwargs = {
            "username": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
        }

    def validate_username(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Введите имя пользователя."
            )

        if CustomUser.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "Пользователь с таким именем уже существует."
            )

        return value

    def validate_email(self, value):
        value = value.lower().strip()

        dvfu_email_regex = (
            r"^[a-zA-Z0-9._%+-]+@"
            r"(?:dvfu\.ru|students\.dvfu\.ru)$"
        )

        if not re.match(dvfu_email_regex, value):
            raise serializers.ValidationError(
                "Разрешены только адреса ДВФУ: "
                "name@dvfu.ru или name@students.dvfu.ru."
            )

        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Пользователь с таким email уже существует."
            )

        return value

    def validate_first_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError("Введите имя.")

        return value

    def validate_last_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError("Введите фамилию.")

        return value

    def validate_middle_name(self, value):
        return value.strip() if value else ""

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if attrs["password"] != attrs["conf_password"]:
            raise serializers.ValidationError(
                {
                    "conf_password": (
                        "Пароль и подтверждение пароля не совпадают."
                    )
                }
            )

        return attrs


class UserRegistrationSerializer(RegistrationDataSerializer):
    """
    Выполняет окончательную регистрацию после проверки кода.
    """

    email_code = serializers.CharField(
        write_only=True,
        required=True,
        max_length=6,
        min_length=6,
        label="Код подтверждения email",
    )

    class Meta(RegistrationDataSerializer.Meta):
        fields = RegistrationDataSerializer.Meta.fields + (
            "email_code",
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        try:
            verify_registration_code(
                email=attrs["email"],
                code=attrs["email_code"],
            )
        except EmailCodeError as error:
            raise serializers.ValidationError(
                {"email_code": str(error)}
            )

        return attrs

    def create(self, validated_data):
        validated_data.pop("conf_password")
        validated_data.pop("email_code")

        password = validated_data.pop("password")

        return CustomUser.objects.create_user(
            password=password,
            **validated_data,
        )
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
