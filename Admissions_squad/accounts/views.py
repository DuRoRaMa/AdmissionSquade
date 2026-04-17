from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Prefetch, Q
from squads.models import SquadMembership
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

    def get_queryset(self):
        queryset = (
            CustomUser.objects.all()
            .order_by("-date_joined")
            .prefetch_related(
                Prefetch(
                    "memberships",
                    queryset=SquadMembership.objects.filter(is_active=True).select_related("role", "squad"),
                    to_attr="active_memberships_prefetched",
                )
            )
        )

        search = (self.request.query_params.get("search") or "").strip()
        is_blocked = (self.request.query_params.get("is_blocked") or "").strip().lower()
        role = (self.request.query_params.get("role") or "").strip()

        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(middle_name__icontains=search)
            )

        if is_blocked in {"true", "false"}:
            queryset = queryset.filter(is_blocked=(is_blocked == "true"))

        if role:
            queryset = queryset.filter(
                memberships__is_active=True
            ).filter(
                Q(memberships__role__name__iexact=role)
                | Q(memberships__role__slug__iexact=role)
            ).distinct()

        return queryset


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