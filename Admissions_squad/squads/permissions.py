from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission

from accounts.permissions import user_has_role_permission
from .models import Squad, SquadMembership


def resolve_squad_from_object(obj):
    if isinstance(obj, Squad):
        return obj
    if isinstance(obj, SquadMembership):
        return obj.squad
    if hasattr(obj, "membership"):
        return obj.membership.squad
    if hasattr(obj, "squad"):
        return obj.squad
    return None


def can_access_membership(user, membership):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    if membership.user_id == user.id:
        return True
    return user_has_role_permission(user, "membership.view_all", squad=membership.squad)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class CanViewSquad(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsSquadCommander(BasePermission):
    def has_object_permission(self, request, view, obj):
        squad = resolve_squad_from_object(obj)
        return bool(squad and user_has_role_permission(request.user, "squad.manage", squad=squad))


class CanManageSquad(BasePermission):
    def has_object_permission(self, request, view, obj):
        squad = resolve_squad_from_object(obj)
        return bool(squad and user_has_role_permission(request.user, "squad.manage", squad=squad))


class CanManageMembershipCreate(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True

        squad_id = view.kwargs.get("squad_id")
        if not squad_id:
            return False

        squad = get_object_or_404(Squad, pk=squad_id)
        return user_has_role_permission(request.user, "membership.create", squad=squad)


class CanViewMembership(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True

        membership_id = view.kwargs.get("pk") or view.kwargs.get("membership_id")
        if not membership_id:
            return True

        membership = get_object_or_404(
            SquadMembership.objects.select_related("squad", "user"),
            pk=membership_id,
        )
        return can_access_membership(request.user, membership)

    def has_object_permission(self, request, view, obj):
        membership = obj if isinstance(obj, SquadMembership) else getattr(obj, "membership", None)
        if membership is None:
            return False
        return can_access_membership(request.user, membership)


class CanManageMembershipUpdate(BasePermission):
    def has_object_permission(self, request, view, obj):
        squad = resolve_squad_from_object(obj)
        return bool(
            squad
            and (
                user_has_role_permission(request.user, "membership.update", squad=squad)
                or user_has_role_permission(request.user, "membership.deactivate", squad=squad)
            )
        )


class CanManageFees(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True

        membership_id = view.kwargs.get("membership_id")
        if not membership_id:
            return False

        membership = get_object_or_404(
            SquadMembership.objects.select_related("squad"),
            pk=membership_id,
        )
        return user_has_role_permission(request.user, "fee.manage", squad=membership.squad)

    def has_object_permission(self, request, view, obj):
        squad = resolve_squad_from_object(obj)
        return bool(squad and user_has_role_permission(request.user, "fee.manage", squad=squad))