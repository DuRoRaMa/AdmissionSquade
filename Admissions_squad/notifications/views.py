from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import SendRegistrationCodeSerializer
from .services import EmailCodeError, send_registration_code


class SendRegistrationCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendRegistrationCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            send_registration_code(serializer.validated_data['email'])
        except EmailCodeError as error:
            return Response(
                {'detail': str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {'message': 'Код подтверждения отправлен на указанную почту.'},
            status=status.HTTP_200_OK,
        )