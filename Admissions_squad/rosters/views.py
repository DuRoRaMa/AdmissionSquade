from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from squads.models import SquadMembership
from .models import (
    AvailabilityForm,
    Schedule,
    ScheduleEntry,
    ScheduleChangeRequest,
)
from .serializers import (
    AvailabilityFormSerializer,
    AvailabilitySubmitSerializer,
    ScheduleSerializer,
    ScheduleEntrySerializer,
    ScheduleChangeRequestSerializer,
)
from .permissions import IsStaffOrCommander
from .services.availability import submit_availability
from .services.generator import generate_schedule
from .services.changes import approve_change_request, reject_change_request
from .services.attendance import create_qr_token, scan_qr


class AvailabilityFormListCreateView(generics.ListCreateAPIView):
    queryset = AvailabilityForm.objects.all().prefetch_related('days__shifts')
    serializer_class = AvailabilityFormSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AvailabilityFormOpenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        form = get_object_or_404(AvailabilityForm, pk=pk)
        form.status = 'open'
        form.save(update_fields=['status'])
        return Response({'message': 'Форма открыта'})


class AvailabilityFormCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        form = get_object_or_404(AvailabilityForm, pk=pk)
        form.status = 'closed'
        form.save(update_fields=['status'])
        return Response({'message': 'Форма закрыта'})


class ActiveAvailabilityFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = SquadMembership.objects.filter(user=request.user, is_active=True).first()
        if not membership:
            return Response({'detail': 'У вас нет активного членства в отряде.'}, status=404)

        form = (
            AvailabilityForm.objects
            .filter(squad=membership.squad, status='open')
            .prefetch_related('days__shifts')
            .order_by('-created_at')
            .first()
        )

        if not form:
            return Response({'detail': 'Нет открытой формы доступности.'}, status=404)

        serializer = AvailabilityFormSerializer(form)
        return Response(serializer.data)


class SubmitAvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        form = get_object_or_404(AvailabilityForm, pk=pk)

        membership = SquadMembership.objects.filter(
            user=request.user,
            squad=form.squad,
            is_active=True
        ).first()

        if not membership:
            return Response({'detail': 'Вы не состоите в этом отряде.'}, status=403)

        if form.status != 'open':
            return Response({'detail': 'Форма не открыта.'}, status=400)

        if form.response_deadline and timezone.now() > form.response_deadline:
            return Response({'detail': 'Срок отправки формы истёк.'}, status=400)

        serializer = AvailabilitySubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            submit_availability(form, membership, serializer.validated_data['slots'])
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)

        return Response({'message': 'Ответ принят'})


class ScheduleListCreateView(generics.ListCreateAPIView):
    queryset = Schedule.objects.all().prefetch_related('needs')
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class GenerateScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        schedule = get_object_or_404(Schedule, pk=pk)

        if schedule.status != 'draft':
            return Response({'detail': 'Генерировать можно только черновик.'}, status=400)

        generate_schedule(schedule)
        return Response({'message': 'Черновик графика сформирован'})


class PublishScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        schedule = get_object_or_404(Schedule, pk=pk)

        if schedule.status != 'draft':
            return Response({'detail': 'Опубликовать можно только черновик.'}, status=400)

        schedule.status = 'published'
        schedule.published_at = timezone.now()
        schedule.save(update_fields=['status', 'published_at'])

        return Response({'message': 'График опубликован'})


class MyScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = SquadMembership.objects.filter(user=request.user, is_active=True).first()
        if not membership:
            return Response([], status=200)

        entries = ScheduleEntry.objects.filter(
            membership=membership,
            schedule__status='published'
        ).select_related('work_block', 'schedule')

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
        return ScheduleChangeRequest.objects.filter(requested_by=self.request.user).order_by('-created_at')


class ChangeRequestListView(generics.ListAPIView):
    queryset = ScheduleChangeRequest.objects.all().select_related('entry', 'requested_by')
    serializer_class = ScheduleChangeRequestSerializer
    permission_classes = [IsAuthenticated]


class ApproveChangeRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        change_request = get_object_or_404(ScheduleChangeRequest, pk=pk)
        try:
            approve_change_request(change_request, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)
        return Response({'message': 'Заявка одобрена'})


class RejectChangeRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        change_request = get_object_or_404(ScheduleChangeRequest, pk=pk)
        reject_change_request(change_request, request.user, request.data.get('review_comment', ''))
        return Response({'message': 'Заявка отклонена'})


class CreateQrTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, entry_id):
        entry = get_object_or_404(ScheduleEntry, pk=entry_id)

        if entry.membership.user_id != request.user.id:
            return Response({'detail': 'Это не ваша смена.'}, status=403)

        token = create_qr_token(entry)
        return Response({
            'message': 'QR-токен создан',
            'token': token.token,
            'expires_at': token.expires_at,
        })


class ScanQrView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token_value = request.data.get('token')
        if not token_value:
            return Response({'detail': 'Токен обязателен.'}, status=400)

        try:
            result = scan_qr(token_value, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)

        return Response(result)