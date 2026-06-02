from rest_framework import serializers

from .models import Notification
from .services import EmailCodeError, validate_registration_email


class SendRegistrationCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            return validate_registration_email(value)
        except EmailCodeError as error:
            raise serializers.ValidationError(str(error))


class NotificationSerializer(serializers.ModelSerializer):
    event_type_label = serializers.CharField(
        source="get_event_type_display",
        read_only=True,
    )

    email_status_label = serializers.CharField(
        source="get_email_status_display",
        read_only=True,
    )

    class Meta:
        model = Notification
        fields = (
            "id",
            "event_type",
            "event_type_label",
            "title",
            "message",
            "object_url",
            "metadata",
            "is_read",
            "read_at",
            "email_required",
            "email_status",
            "email_status_label",
            "email_sent_at",
            "email_error",
            "created_at",
        )
        read_only_fields = fields
