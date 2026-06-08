
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
# Create your views here.
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from .serializers import (
    CustomTokenObtainPairSerializer,
    RegistrationDataSerializer,
    UserRegistrationSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)
from rest_framework.views import APIView
from accounts.models import CustomUser
from notifications.services import (
    EmailCodeError,
    send_registration_code,
)

class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegistrationStartView(APIView):
    """
    Проверяет все поля регистрации и только после успешной
    проверки отправляет код на электронную почту.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistrationDataSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        try:
            send_registration_code(email)
        except EmailCodeError as error:
            # Ошибка будет показана непосредственно у поля email.
            raise ValidationError(
                {"email": [str(error)]}
            )

        return Response(
            {
                "message": (
                    "Данные успешно проверены. "
                    "Код подтверждения отправлен на почту."
                )
            },
            status=status.HTTP_200_OK,
        )


class RegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response(
            {
                "message": "Пользователь успешно создан.",
                "data": {
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            },
            status=status.HTTP_201_CREATED,
        )
    
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user = CustomUser.objects.filter(email=email, is_active=True).first()

        # Важно: даже если пользователя нет, возвращаем успешный ответ.
        # Так нельзя будет проверить, зарегистрирована ли почта в системе.
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            reset_url = (
                f'{settings.FRONTEND_URL}/reset-password'
                f'?uid={uid}&token={token}'
            )

            send_mail(
                subject='Восстановление пароля',
                message=(
                    'Для восстановления пароля перейдите по ссылке:\n\n'
                    f'{reset_url}\n\n'
                    'Если вы не запрашивали восстановление пароля, просто проигнорируйте это письмо.'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

        return Response(
            {
                'message': (
                    'Если пользователь с такой почтой существует, '
                    'на нее отправлена ссылка для восстановления пароля.'
                )
            },
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {'message': 'Пароль успешно изменен.'},
            status=status.HTTP_200_OK,
        )

