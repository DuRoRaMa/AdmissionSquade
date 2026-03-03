from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .serializers import UserRegistrationSerializer, ProfileUserSerializer
from .models import CustomUser
# Create your views here.


class RegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'massage': 'Пользователь успешно создан'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileUserSerializer

    def get_object(self):
        return self.request.user
    
    def get_queryset(self):
        # Оптимизация загрузки связанных данных
        return CustomUser.objects.filter(pk=self.request.user.pk).prefetch_related(
            'membersips__squad',      # загружаем отряды для каждого членства
            'membersips__role',        # загружаем роли
            'membersips__fees',        # загружаем взносы для каждого членства
        )
    
