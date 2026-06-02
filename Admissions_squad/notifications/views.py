from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .email_service import send_notification_email
from .models import Notification
from .serializers import NotificationSerializer, SendRegistrationCodeSerializer
from .services import EmailCodeError, send_registration_code


class SendRegistrationCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendRegistrationCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            send_registration_code(serializer.validated_data["email"])
        except EmailCodeError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Код подтверждения отправлен на указанную почту."},
            status=status.HTTP_200_OK,
        )


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Notification.objects.filter(
            recipient=self.request.user,
        )

        only_unread = str(
            self.request.query_params.get("unread", "")
        ).lower() in {"1", "true", "yes"}

        if only_unread:
            queryset = queryset.filter(is_read=False)

        return queryset.order_by("-created_at")[:50]


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count()

        return Response({"count": count})


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = Notification.objects.filter(
            pk=pk,
            recipient=request.user,
        ).first()

        if not notification:
            return Response(
                {"detail": "Уведомление не найдено."},
                status=status.HTTP_404_NOT_FOUND,
            )

        notification.mark_as_read()

        serializer = NotificationSerializer(notification)

        return Response(serializer.data)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        notifications = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        )

        for notification in notifications:
            notification.mark_as_read()

        return Response({"message": "Уведомления отмечены как прочитанные."})


class NotificationRetryEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = Notification.objects.filter(
            pk=pk,
            recipient=request.user,
        ).first()

        if not notification:
            return Response(
                {"detail": "Уведомление не найдено."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not notification.email_required:
            return Response(
                {"detail": "Для этого уведомления email-отправка не требуется."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        send_notification_email(notification)

        serializer = NotificationSerializer(notification)

        return Response(serializer.data)
