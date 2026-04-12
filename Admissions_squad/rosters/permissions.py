from rest_framework.permissions import BasePermission
from squads.models import SquadMembership


class IsStaffOrCommander(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        squad = getattr(obj, 'squad', None)
        if squad is None and hasattr(obj, 'form'):
            squad = obj.form.squad
        if squad is None and hasattr(obj, 'schedule'):
            squad = obj.schedule.squad
        if squad is None and hasattr(obj, 'entry'):
            squad = obj.entry.schedule.squad
        if squad is None:
            return False

        return SquadMembership.objects.filter(
            user=request.user,
            squad=squad,
            role__slug='commander',
            is_active=True
        ).exists()


class IsOwnMembershipData(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        membership = getattr(obj, 'membership', None)
        if membership is None and hasattr(obj, 'entry'):
            membership = obj.entry.membership
        return membership and membership.user_id == request.user.id