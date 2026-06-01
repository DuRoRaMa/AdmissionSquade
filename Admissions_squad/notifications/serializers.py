from rest_framework import serializers

from .services import EmailCodeError, validate_registration_email


class SendRegistrationCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            return validate_registration_email(value)
        except EmailCodeError as error:
            raise serializers.ValidationError(str(error))