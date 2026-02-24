
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from accounts.models import CustomUser
# Create your views here.


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
