import csv
from decimal import Decimal

from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.companies.mixins import CompanyScopedMixin
from .models import Project, Milestone, Task, BudgetEntry
from .serializers import ProjectSerializer, MilestoneSerializer, TaskSerializer, BudgetEntrySerializer


class ProjectViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Project.objects.select_related('manager').prefetch_related('team_members').all()
    serializer_class = ProjectSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['name', 'project_code', 'client']
    filterset_fields = ['status', 'priority', 'manager']
    ordering_fields = ['start_date', 'end_date', 'budget', 'created_at']

    @action(detail=True, methods=['get', 'post'], url_path='milestones')
    def milestones(self, request, pk=None):
        project = self.get_object()
        if request.method == 'POST':
            ser = MilestoneSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save(project=project, company=project.company)
            return Response(ser.data, status=status.HTTP_201_CREATED)
        qs = project.milestones.all()
        return Response(MilestoneSerializer(qs, many=True).data)

    @action(detail=True, methods=['get', 'post'], url_path='tasks')
    def tasks_list(self, request, pk=None):
        project = self.get_object()
        if request.method == 'POST':
            ser = TaskSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save(project=project, company=project.company)
            return Response(ser.data, status=status.HTTP_201_CREATED)
        qs = project.tasks.select_related('assigned_to', 'milestone').all()
        return Response(TaskSerializer(qs, many=True).data)

    @action(detail=True, methods=['get', 'post'], url_path='budget')
    def budget(self, request, pk=None):
        project = self.get_object()
        if request.method == 'POST':
            ser = BudgetEntrySerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save(project=project, company=project.company)
            return Response(ser.data, status=status.HTTP_201_CREATED)
        qs = project.budget_entries.all()
        return Response(BudgetEntrySerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        projects = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="projects-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Code', 'Name', 'Client', 'Status', 'Priority', 'Start', 'End', 'Budget', 'Actual Cost', 'Progress', 'Manager'])
        for p in projects:
            writer.writerow([p.project_code, p.name, p.client, p.status, p.priority, p.start_date, p.end_date, p.budget, p.actual_cost, p.progress, p.manager.get_full_name() if p.manager_id else ''])
        return response

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        today = timezone.now().date()
        qs = self.get_queryset()
        total_budget = qs.aggregate(t=Sum('budget'))['t'] or Decimal('0')
        total_actual_cost = qs.aggregate(t=Sum('actual_cost'))['t'] or Decimal('0')
        overdue_milestones = self.company_scope(Milestone.objects.all()).filter(due_date__lt=today).exclude(status='completed').count()
        tasks_due_today = self.company_scope(Task.objects.all()).filter(due_date=today).exclude(status='done').count()
        return Response({
            'total_projects': qs.count(),
            'active_projects': qs.filter(status='active').count(),
            'completed_projects': qs.filter(status='completed').count(),
            'on_hold_projects': qs.filter(status='on_hold').count(),
            'total_budget': float(total_budget),
            'total_actual_cost': float(total_actual_cost),
            'overdue_milestones': overdue_milestones,
            'tasks_due_today': tasks_due_today,
        })


class MilestoneViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Milestone.objects.select_related('project').all()
    serializer_class = MilestoneSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['project', 'status']


class TaskViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Task.objects.select_related('project', 'milestone', 'assigned_to').all()
    serializer_class = TaskSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['project', 'milestone', 'status', 'assigned_to']


class BudgetEntryViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = BudgetEntry.objects.select_related('project').all()
    serializer_class = BudgetEntrySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['project', 'category']
