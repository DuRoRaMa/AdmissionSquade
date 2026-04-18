from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from squads.models import SquadMembership
from .models import (
    AvailabilityForm,
    Schedule,
    ScheduleEntry,
    ScheduleChangeRequest,
    QrToken,
)
from .serializers import (
    AvailabilityFormSerializer,
    AvailabilitySubmitSerializer,
    ScheduleSerializer,
    ScheduleEntrySerializer,
    ScheduleChangeRequestSerializer,
)
from .permissions import (
    can_manage_availability,
    can_respond_own_availability,
    can_manage_roster,
    can_publish_roster,
    can_view_roster_all,
    can_view_own_roster,
    get_squad_ids_with_permission,
    get_user_active_memberships,
)
from .services.availability import submit_availability
from .services.generator import generate_schedule
from .services.changes import approve_change_request, reject_change_request
from .services.attendance import create_qr_token, scan_qr


class AvailabilityFormListCreateView(generics.ListCreateAPIView):
    serializer_class = AvailabilityFormSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            AvailabilityForm.objects
            .all()
            .prefetch_related("days__shifts")
            .select_related("squad", "created_by")
        )

        if self.request.user.is_staff:
            return queryset

        squad_ids = get_squad_ids_with_permission(
            self.request.user,
            ["availability.manage"],
        )
        return queryset.filter(squad_id__in=squad_ids)

    def perform_create(self, serializer):
        squad = serializer.validated_data["squad"]

        if not can_manage_availability(self.request.user, squad):
            raise PermissionDenied("Недостаточно прав для создания формы доступности.")

        serializer.save(created_by=self.request.user)


class AvailabilityFormOpenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        form = get_object_or_404(AvailabilityForm, pk=pk)

        if not can_manage_availability(request.user, form.squad):
            raise PermissionDenied("Недостаточно прав для открытия формы доступности.")

        form.status = "open"
        form.save(update_fields=["status"])
        return Response({"message": "Форма открыта"})


class AvailabilityFormCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        form = get_object_or_404(AvailabilityForm, pk=pk)

        if not can_manage_availability(request.user, form.squad):
            raise PermissionDenied("Недостаточно прав для закрытия формы доступности.")

        form.status = "closed"
        form.save(update_fields=["status"])
        return Response({"message": "Форма закрыта"})


class ActiveAvailabilityFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        squad_id = request.query_params.get("squad")

        memberships = get_user_active_memberships(request.user)
        if squad_id:
            memberships = memberships.filter(squad_id=squad_id)

        allowed_memberships = [
            membership
            for membership in memberships
            if can_respond_own_availability(request.user, membership.squad)
        ]

        if not allowed_memberships:
            return Response(
                {"detail": "У вас нет активного доступа к форме доступности."},
                status=404,
            )

        squad = allowed_memberships[0].squad
        form = (
            AvailabilityForm.objects
            .filter(squad=squad, status="open")
            .prefetch_related("days__shifts")
            .order_by("-created_at")
            .first()
        )

        if not form:
            return Response({"detail": "Нет открытой формы доступности."}, status=404)

        serializer = AvailabilityFormSerializer(form)
        return Response(serializer.data)


class SubmitAvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        form = get_object_or_404(AvailabilityForm, pk=pk)

        membership = SquadMembership.objects.filter(
            user=request.user,
            squad=form.squad,
            is_active=True,
        ).first()

        if not membership:
            return Response({"detail": "Вы не состоите в этом отряде."}, status=403)

        if not can_respond_own_availability(request.user, form.squad):
            raise PermissionDenied("Недостаточно прав для отправки доступности.")

        if form.status != "open":
            return Response({"detail": "Форма не открыта."}, status=400)

        if form.response_deadline and timezone.now() > form.response_deadline:
            return Response({"detail": "Срок отправки формы истёк."}, status=400)

        serializer = AvailabilitySubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            submit_availability(form, membership, serializer.validated_data["slots"])
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        return Response({"message": "Ответ принят"})


class ScheduleListCreateView(generics.ListCreateAPIView):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            Schedule.objects
            .all()
            .prefetch_related("needs")
            .select_related("squad", "created_by")
        )

        if self.request.user.is_staff:
            return queryset

        squad_ids = get_squad_ids_with_permission(
            self.request.user,
            ["roster.view_all", "roster.manage", "roster.publish"],
        )
        return queryset.filter(squad_id__in=squad_ids)

    def perform_create(self, serializer):
        squad = serializer.validated_data["squad"]

        if not can_manage_roster(self.request.user, squad):
            raise PermissionDenied("Недостаточно прав для создания графика.")

        serializer.save(created_by=self.request.user)


class GenerateScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        schedule = get_object_or_404(Schedule, pk=pk)

        if not can_manage_roster(request.user, schedule.squad):
            raise PermissionDenied("Недостаточно прав для генерации графика.")

        if schedule.status != "draft":
            return Response({"detail": "Генерировать можно только черновик."}, status=400)

        generate_schedule(schedule)
        return Response({"message": "Черновик графика сформирован"})


class PublishScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        schedule = get_object_or_404(Schedule, pk=pk)

        if not can_publish_roster(request.user, schedule.squad):
            raise PermissionDenied("Недостаточно прав для публикации графика.")

        if schedule.status != "draft":
            return Response({"detail": "Опубликовать можно только черновик."}, status=400)

        schedule.status = "published"
        schedule.published_at = timezone.now()
        schedule.save(update_fields=["status", "published_at"])

        return Response({"message": "График опубликован"})


class MyScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            queryset = (
                ScheduleEntry.objects
                .filter(schedule__status="published")
                .select_related("work_block", "schedule", "membership__user", "membership__squad")
            )
            serializer = ScheduleEntrySerializer(queryset, many=True)
            return Response(serializer.data)

        allowed_membership_ids = [
            membership.id
            for membership in get_user_active_memberships(request.user)
            if can_view_own_roster(request.user, membership.squad)
        ]

        if not allowed_membership_ids:
            return Response([], status=200)

        entries = (
            ScheduleEntry.objects
            .filter(
                membership_id__in=allowed_membership_ids,
                schedule__status="published",
            )
            .select_related("work_block", "schedule", "membership__user", "membership__squad")
        )

        serializer = ScheduleEntrySerializer(entries, many=True)
        return Response(serializer.data)


class ChangeRequestCreateView(generics.CreateAPIView):
    serializer_class = ScheduleChangeRequestSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)


class MyChangeRequestsView(generics.ListAPIView):
    serializer_class = ScheduleChangeRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            ScheduleChangeRequest.objects
            .filter(requested_by=self.request.user)
            .select_related(
                "entry",
                "entry__schedule",
                "entry__membership",
                "entry__membership__user",
                "target_membership",
                "reviewed_by",
            )
            .order_by("-created_at")
        )


class ChangeRequestListView(generics.ListAPIView):
    serializer_class = ScheduleChangeRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            ScheduleChangeRequest.objects
            .all()
            .select_related(
                "entry",
                "entry__schedule",
                "entry__schedule__squad",
                "entry__membership",
                "requested_by",
                "target_membership",
                "reviewed_by",
            )
            .order_by("-created_at")
        )

        if self.request.user.is_staff:
            return queryset

        squad_ids = get_squad_ids_with_permission(self.request.user, "roster.manage")
        return queryset.filter(entry__schedule__squad_id__in=squad_ids)


class ApproveChangeRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        change_request = get_object_or_404(
            ScheduleChangeRequest.objects.select_related("entry__schedule__squad"),
            pk=pk,
        )

        if not can_manage_roster(request.user, change_request.entry.schedule.squad):
            raise PermissionDenied("Недостаточно прав для одобрения заявки.")

        try:
            approve_change_request(change_request, request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        return Response({"message": "Заявка одобрена"})


class RejectChangeRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        change_request = get_object_or_404(
            ScheduleChangeRequest.objects.select_related("entry__schedule__squad"),
            pk=pk,
        )

        if not can_manage_roster(request.user, change_request.entry.schedule.squad):
            raise PermissionDenied("Недостаточно прав для отклонения заявки.")

        reject_change_request(
            change_request,
            request.user,
            request.data.get("review_comment", ""),
        )
        return Response({"message": "Заявка отклонена"})


class CreateQrTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, entry_id):
        entry = get_object_or_404(
            ScheduleEntry.objects.select_related("membership__user"),
            pk=entry_id,
        )

        if entry.membership.user_id != request.user.id and not request.user.is_staff:
            return Response({"detail": "Это не ваша смена."}, status=403)

        token = create_qr_token(entry)
        return Response(
            {
                "message": "QR-токен создан",
                "token": token.token,
                "expires_at": token.expires_at,
            }
        )


class ScanQrView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token_value = request.data.get("token")
        if not token_value:
            return Response({"detail": "Токен обязателен."}, status=400)

        token = get_object_or_404(
            QrToken.objects.select_related("entry__schedule__squad"),
            token=token_value,
        )

        if not can_manage_roster(request.user, token.entry.schedule.squad):
            raise PermissionDenied("Недостаточно прав для отметки прихода или ухода.")

        try:
            result = scan_qr(token_value, request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        return Response(result)