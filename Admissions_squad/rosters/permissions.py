from rest_framework.permissions import BasePermission

from accounts.permissions import user_has_role_permission
from squads.models import SquadMembership


def get_user_active_memberships(user):
    if not user or not user.is_authenticated:
        return SquadMembership.objects.none()

    return (
        SquadMembership.objects
        .filter(user=user, is_active=True)
        .select_related("role", "squad", "user")
    )


def get_squad_ids_with_permission(user, permission_codes):
    if not user or not user.is_authenticated:
        return []

    if user.is_staff:
        return []

    if isinstance(permission_codes, str):
        permission_codes = [permission_codes]

    squad_ids = []
    for membership in get_user_active_memberships(user):
        if any(
            user_has_role_permission(user, code, squad=membership.squad)
            for code in permission_codes
        ):
            squad_ids.append(membership.squad_id)

    return sorted(set(squad_ids))


def get_user_membership_in_squad(user, squad):
    if not user or not user.is_authenticated:
        return None

    return get_user_active_memberships(user).filter(squad=squad).first()


def resolve_squad_from_object(obj):
    if hasattr(obj, "squad") and obj.squad is not None:
        return obj.squad

    if hasattr(obj, "form") and getattr(obj.form, "squad", None) is not None:
        return obj.form.squad

    if hasattr(obj, "schedule") and getattr(obj.schedule, "squad", None) is not None:
        return obj.schedule.squad

    if hasattr(obj, "entry") and getattr(obj.entry, "schedule", None) is not None:
        return obj.entry.schedule.squad

    if hasattr(obj, "membership") and getattr(obj.membership, "squad", None) is not None:
        return obj.membership.squad

    return None


def can_manage_availability(user, squad):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_staff
            or user_has_role_permission(user, "availability.manage", squad=squad)
        )
    )


def can_view_availability(user, squad):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_staff
            or user_has_role_permission(user, "availability.view_all", squad=squad)
            or user_has_role_permission(user, "availability.manage", squad=squad)
        )
    )


def can_respond_own_availability(user, squad):
    membership = get_user_membership_in_squad(user, squad)

    return bool(
        membership
        and (
            user.is_staff
            or user_has_role_permission(user, "availability.respond_own", squad=squad)
        )
    )


def can_manage_roster(user, squad):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_staff
            or user_has_role_permission(user, "roster.manage", squad=squad)
        )
    )


def can_publish_roster(user, squad):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_staff
            or user_has_role_permission(user, "roster.publish", squad=squad)
        )
    )


def can_view_roster_all(user, squad):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_staff
            or user_has_role_permission(user, "roster.view_all", squad=squad)
            or user_has_role_permission(user, "roster.manage", squad=squad)
            or user_has_role_permission(user, "roster.publish", squad=squad)
        )
    )


def can_view_own_roster(user, squad):
    membership = get_user_membership_in_squad(user, squad)

    return bool(
        membership
        and (
            user.is_staff
            or user_has_role_permission(user, "roster.view_own", squad=squad)
        )
    )


class IsOwnMembershipData(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        membership = getattr(obj, "membership", None)
        if membership is None and hasattr(obj, "entry"):
            membership = obj.entry.membership

        return bool(membership and membership.user_id == request.user.id)


class HasRosterManageObjectPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        squad = resolve_squad_from_object(obj)
        return bool(squad and can_manage_roster(request.user, squad))


class HasRosterPublishObjectPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        squad = resolve_squad_from_object(obj)
        return bool(squad and can_publish_roster(request.user, squad))


class HasAvailabilityManageObjectPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        squad = resolve_squad_from_object(obj)
        return bool(squad and can_manage_availability(request.user, squad))