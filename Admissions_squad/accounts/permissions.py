from rest_framework.permissions import SAFE_METHODS, BasePermission


def get_user_active_membership(user, squad=None):
    if not user or not user.is_authenticated:
        return None

    queryset = user.memberships.filter(is_active=True).select_related("role", "squad")
    if squad is not None:
        queryset = queryset.filter(squad=squad)

    return queryset.first()


def get_user_role_permissions(user, squad=None):
    if not user or not user.is_authenticated:
        return set()

    if user.is_staff:
        return {"*"}

    queryset = user.memberships.filter(is_active=True).select_related("role", "squad")
    if squad is not None:
        queryset = queryset.filter(squad=squad)

    permissions = set()
    for membership in queryset:
        if membership.role:
            permissions.update(membership.role.get_all_permissions())

    return permissions


def user_has_role_permission(user, permission_code, squad=None):
    permissions = get_user_role_permissions(user, squad=squad)
    return "*" in permissions or permission_code in permissions


class IsAdmin(BasePermission):
    """Только глобальный администратор системы."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsSelfOrAdmin(BasePermission):
    """Доступ для самого пользователя или администратора."""

    def has_object_permission(self, request, view, obj):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or obj == request.user)
        )


class IsAdminOrReadOnly(BasePermission):
    """Чтение разрешено аутентифицированным, запись только администратору."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)