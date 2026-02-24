from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from accounts.models import CustomUser


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        data = super().validate(attrs)
        return data
