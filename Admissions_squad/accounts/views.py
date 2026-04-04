from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from .models import CustomUser, Role
from .serializers import (
    ProfileUserSerializer, UserListSerializer, UserDetailSerializer,
    UserUpdateSerializer, ChangePasswordSerializer, RoleSerializer
)
from .permissions import IsAdmin, IsSelfOrAdmin, IsAdminOrReadOnly

class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileUserSerializer

    def get_object(self):
        return self.request.user

class UserListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = UserListSerializer
    queryset = CustomUser.objects.all().order_by('-date_joined')
    
    def get_queryset(self):
        qs = super().get_queryset()
        # Фильтрация по параметрам запроса
        role = self.request.query_params.get('role')
        if role:
            # фильтрация по роли (через членства)
            qs = qs.filter(membersips__role__name=role).distinct()
        squad = self.request.query_params.get('squad')
        if squad:
            qs = qs.filter(membersips__squad__id=squad).distinct()
        is_blocked = self.request.query_params.get('is_blocked')
        if is_blocked is not None:
            qs = qs.filter(is_blocked=is_blocked.lower() == 'true')
        return qs

# --- Детали пользователя (админ или сам пользователь) ---
class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsSelfOrAdmin]
    queryset = CustomUser.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserDetailSerializer
    
    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        # Вместо удаления делаем деактивацию (блокировку)
        user.is_active = False
        user.is_blocked = True
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

# --- Смена пароля текущего пользователя ---
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'detail': 'Пароль успешно изменён.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# --- CRUD для ролей (только админ) ---
class RoleListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = Role.objects.all()
    serializer_class = RoleSerializer

class RoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
