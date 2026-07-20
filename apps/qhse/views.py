import csv

from django.db.models import Avg
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.companies.mixins import CompanyScopedMixin
from .models import Incident, Inspection, RiskRegister, SafetyChecklist, ChecklistItem, ComplianceRecord
from .serializers import (
    IncidentSerializer, InspectionSerializer, RiskRegisterSerializer,
    SafetyChecklistSerializer, ChecklistItemSerializer, ComplianceRecordSerializer,
)


class IncidentViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Incident.objects.select_related('reported_by').all()
    serializer_class = IncidentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['incident_number', 'title', 'location']
    filterset_fields = ['incident_type', 'severity', 'status']
    ordering_fields = ['date', 'created_at']

    def perform_create(self, serializer):
        company, _ = self._company_context()
        serializer.save(reported_by=self.request.user, company=company)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        incidents = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="incidents-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Number', 'Title', 'Type', 'Severity', 'Date', 'Location', 'Status', 'Reported By'])
        for i in incidents:
            writer.writerow([i.incident_number, i.title, i.incident_type, i.severity, i.date, i.location, i.status, i.reported_by.get_full_name() if i.reported_by_id else ''])
        return response


class InspectionViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Inspection.objects.select_related('conducted_by').all()
    serializer_class = InspectionSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['title', 'location']
    filterset_fields = ['inspection_type', 'status']
    ordering_fields = ['scheduled_date', 'completed_date']


class RiskRegisterViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = RiskRegister.objects.select_related('owner').all()
    serializer_class = RiskRegisterSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['risk_id', 'title']
    filterset_fields = ['category', 'risk_level', 'status']
    ordering_fields = ['risk_score', 'review_date']


class SafetyChecklistViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = SafetyChecklist.objects.select_related('created_by').prefetch_related('items').all()
    serializer_class = SafetyChecklistSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['title', 'location']
    filterset_fields = ['checklist_type', 'status']
    ordering_fields = ['date']

    def perform_create(self, serializer):
        company, _ = self._company_context()
        serializer.save(created_by=self.request.user, company=company)


class ChecklistItemViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = ChecklistItem.objects.select_related('checklist').all()
    serializer_class = ChecklistItemSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['checklist']


class ComplianceRecordViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = ComplianceRecord.objects.select_related('responsible_person').all()
    serializer_class = ComplianceRecordSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['title']
    filterset_fields = ['compliance_type', 'status']
    ordering_fields = ['due_date']


class QHSEDashboardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.companies.utils import resolve_company, get_company_queryset
        company, is_platform_admin = resolve_company(request)
        def scoped(qs):
            return get_company_queryset(qs, company, is_platform_admin)

        today = timezone.now().date()
        month_start = today.replace(day=1)
        ninety_days_ago = today - timezone.timedelta(days=90)

        incidents_qs = scoped(Incident.objects.all())
        risks_qs = scoped(RiskRegister.objects.all())
        inspections_qs = scoped(Inspection.objects.all())
        compliance_qs = scoped(ComplianceRecord.objects.all())

        open_incidents = incidents_qs.exclude(status__in=['closed', 'resolved']).count()
        incidents_this_month = incidents_qs.filter(date__gte=month_start, date__lte=today).count()
        high_critical_risks = risks_qs.filter(risk_level__in=['high', 'critical']).exclude(status__in=['closed', 'mitigated']).count()
        scheduled_inspections = inspections_qs.filter(status='scheduled').count()
        overdue_compliance = compliance_qs.filter(due_date__lt=today).exclude(status='compliant').count()

        recent_scores = inspections_qs.filter(
            status='completed', score__isnull=False, completed_date__gte=ninety_days_ago,
        ).aggregate(avg=Avg('score'))['avg']
        if recent_scores is None:
            recent_scores = inspections_qs.filter(status='completed', score__isnull=False).aggregate(avg=Avg('score'))['avg']
        safety_score = round(recent_scores) if recent_scores is not None else 100

        return Response({
            'open_incidents': open_incidents,
            'incidents_this_month': incidents_this_month,
            'high_critical_risks': high_critical_risks,
            'scheduled_inspections': scheduled_inspections,
            'overdue_compliance': overdue_compliance,
            'safety_score': safety_score,
            'recent_incidents': IncidentSerializer(incidents_qs.select_related('reported_by').order_by('-date', '-id')[:5], many=True).data,
            'upcoming_inspections': InspectionSerializer(inspections_qs.filter(status='scheduled').order_by('scheduled_date')[:5], many=True).data,
        })
