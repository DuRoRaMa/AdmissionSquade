from rest_framework import generics, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from .models import Squad, SquadMembership, MembershipFee
from .serializers import (
    SquadSerializer, SquadMembershipSerializer, MembershipFeeSerializer
)
from .permissions import (
    IsAdmin, CanManageSquad, CanManageMembershipCreate, CanViewMembership,
    CanManageMembershipUpdate, CanManageFees
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ----- Отряды (Squad) -----
class SquadListCreateView(generics.ListCreateAPIView):
    serializer_class = SquadSerializer
    queryset = Squad.objects.all().order_by('-created_at')
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.request.method == 'POST':
            # Создание отряда – только администратор
            return [IsAuthenticated(), IsAdmin()]
        # GET – любой аутентифицированный
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save()


class SquadDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SquadSerializer
    queryset = Squad.objects.all()

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        # Изменение/удаление – админ или командир
        return [IsAuthenticated(), CanManageSquad()]

    def destroy(self, request, *args, **kwargs):
        squad = self.get_object()
        if squad.memberships.filter(is_active=True).exists():
            return Response({'detail': 'Нельзя удалить отряд с активными участниками.'},
                            status=status.HTTP_400_BAD_REQUEST)
        squad.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ----- Членство в отряде (SquadMembership) -----
class SquadMembershipListCreateView(generics.ListCreateAPIView):
    serializer_class = SquadMembershipSerializer
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), CanManageMembershipCreate()]
        return [IsAuthenticated()]

    def get_queryset(self):
        squad_id = self.kwargs.get("squad_id")
        if squad_id:
            return (
                SquadMembership.objects.filter(squad_id=squad_id, is_active=True)
                .select_related("user", "role", "squad")
            )
        return SquadMembership.objects.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        squad_id = self.kwargs.get("squad_id")
        if squad_id:
            context["squad"] = get_object_or_404(Squad, pk=squad_id)
        return context

    def perform_create(self, serializer):
        from accounts.permissions import user_has_role_permission
        from accounts.models import Role

        squad = self.get_serializer_context()["squad"]
        requested_user = serializer.validated_data.get("user")

        is_manager = (
            self.request.user.is_staff
            or user_has_role_permission(self.request.user, "squad.manage", squad=squad)
            or user_has_role_permission(self.request.user, "membership.manage", squad=squad)
        )

        if requested_user and requested_user != self.request.user and is_manager:
            user_to_assign = requested_user
        else:
            user_to_assign = self.request.user

        role_to_assign = serializer.validated_data.get("role") or Role.get_or_create_default_member_role()

        serializer.save(
            squad=squad,
            user=user_to_assign,
            role=role_to_assign,
        )


class SquadMembershipDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SquadMembershipSerializer
    queryset = SquadMembership.objects.all().select_related('user', 'role', 'squad')

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated(), CanViewMembership()]
        elif self.request.method in ['PUT', 'PATCH']:
            return [IsAuthenticated(), CanManageMembershipUpdate()]
        elif self.request.method == 'DELETE':
            # Деактивация – доступна командиру, админу или самому участнику
            return [IsAuthenticated(), CanViewMembership()]  # CanViewMembership включает самого пользователя

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        membership.is_active = False
        membership.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ----- Членские взносы (MembershipFee) -----
class MembershipFeeListCreateView(generics.ListCreateAPIView):
    serializer_class = MembershipFeeSerializer
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), CanManageFees()]
        # GET – просмотр взносов участника, используем проверку доступа к членству
        return [IsAuthenticated(), CanViewMembership()]

    def get_queryset(self):
        membership_id = self.kwargs.get('membership_id')
        if membership_id:
            return MembershipFee.objects.filter(membership_id=membership_id).select_related('membership')
        return MembershipFee.objects.none()

    def perform_create(self, serializer):
        membership_id = self.kwargs.get('membership_id')
        membership = get_object_or_404(SquadMembership, pk=membership_id)
        serializer.save(membership=membership)


class MembershipFeeDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MembershipFeeSerializer
    queryset = MembershipFee.objects.all()

    def get_permissions(self):
        if self.request.method == 'GET':
            # Просмотр – через CanViewMembership (проверка на объекте)
            return [IsAuthenticated(), CanViewMembership()]
        elif self.request.method in ['PUT', 'PATCH']:
            # Обновление – админ или командир
            return [IsAuthenticated(), CanManageFees()]
        elif self.request.method == 'DELETE':
            # Удаление – только администратор
            return [IsAuthenticated(), IsAdmin()]