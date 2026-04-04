from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAdmin(BasePermission):
    """Только администраторы (is_staff = True)."""
    def has_permission(self, request, view):
        return request.user and request.user.is_staff

class IsSelfOrAdmin(BasePermission):
    """Доступ для самого пользователя или администратора."""
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj == request.user

class IsAdminOrReadOnly(BasePermission):
    """Чтение разрешено всем аутентифицированным, запись – только админам."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_staff