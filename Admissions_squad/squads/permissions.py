from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAdmin(BasePermission):
    """Только администраторы (is_staff=True)."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff


class CanViewSquad(BasePermission):
    """Просмотр отряда доступен любому аутентифицированному."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsSquadCommander(BasePermission):
    """Проверка, является ли пользователь командиром данного отряда."""
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        # Определяем отряд
        if hasattr(obj, 'squad'):
            squad = obj.squad
        elif hasattr(obj, 'membership'):
            squad = obj.membership.squad
        else:
            squad = obj
        return squad.memberships.filter(
            user=request.user,
            role__name__in=['Командир', 'Commander'],
            is_active=True
        ).exists()


class CanManageSquad(BasePermission):
    """Управление отрядом (изменение, удаление) – админ или командир."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return IsSquadCommander().has_object_permission(request, view, obj)


class CanManageMembershipCreate(BasePermission):
    """Создание членства – только админ или командир отряда."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        squad_id = view.kwargs.get('squad_id')
        if squad_id:
            from .models import Squad
            try:
                squad = Squad.objects.get(pk=squad_id)
                return squad.memberships.filter(
                    user=request.user,
                    role__name__in=['Командир', 'Commander'],
                    is_active=True
                ).exists()
            except Squad.DoesNotExist:
                return False
        return False


class CanViewMembership(BasePermission):
    """Просмотр членства: админ, командир отряда или сам участник."""
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        if obj.user == request.user:
            return True
        # Командир отряда
        return obj.squad.memberships.filter(
            user=request.user,
            role__name__in=['Командир', 'Commander'],
            is_active=True
        ).exists()


class CanManageMembershipUpdate(BasePermission):
    """Изменение членства (роль, билет, деактивация) – админ или командир."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.squad.memberships.filter(
            user=request.user,
            role__name__in=['Командир', 'Commander'],
            is_active=True
        ).exists()


class CanManageFees(BasePermission):
    """Создание и изменение взносов – админ или командир (без казначея)."""
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        squad = obj.membership.squad
        return squad.memberships.filter(
            user=request.user,
            role__name__in=['Командир', 'Commander'],
            is_active=True
        ).exists()

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        membership_id = view.kwargs.get('membership_id')
        if membership_id:
            from .models import SquadMembership
            try:
                membership = SquadMembership.objects.get(pk=membership_id)
                squad = membership.squad
                return squad.memberships.filter(
                    user=request.user,
                    role__name__in=['Командир', 'Commander'],
                    is_active=True
                ).exists()
            except SquadMembership.DoesNotExist:
                return False
        return False