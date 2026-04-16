from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CustomUser, Passport, Role, UserStudyInfo
from .permissions import IsAdmin, IsSelfOrAdmin
from .serializers import (
    ChangePasswordSerializer,
    PassportSerializer,
    ProfileUserSerializer,
    RoleSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserStudyInfoSerializer,
    UserUpdateSerializer,
)


class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileUserSerializer

    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = UserListSerializer
    queryset = CustomUser.objects.all().order_by("-date_joined")


class UserDetailView(generics.RetrieveUpdateAPIView):
    queryset = CustomUser.objects.all()

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated(), IsSelfOrAdmin()]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserUpdateSerializer
        return UserDetailSerializer


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        return Response({"detail": "Пароль успешно изменен."}, status=status.HTTP_200_OK)


class RolePermissionCatalogView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response(Role.permission_catalog(), status=status.HTTP_200_OK)


class RoleListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = RoleSerializer
    queryset = Role.objects.select_related("parent").all().order_by("name")


class RoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = RoleSerializer
    queryset = Role.objects.select_related("parent").all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.is_system:
            return Response(
                {"detail": "Системную роль нельзя удалить."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if instance.children.exists():
            return Response(
                {"detail": "Нельзя удалить роль, у которой есть дочерние роли."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if instance.squadmembership_set.filter(is_active=True).exists():
            return Response(
                {"detail": "Нельзя удалить роль, которая назначена активным участникам."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)


class UserStudyInfoView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserStudyInfoSerializer

    def get_object(self):
        return get_object_or_404(UserStudyInfo, user=self.request.user)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PassportView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PassportSerializer

    def get_object(self):
        return get_object_or_404(Passport, user=self.request.user)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)