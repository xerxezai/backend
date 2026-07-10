from decimal import Decimal

from django.db.models import Sum, Count
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Customer, Contact, Lead, Activity, Deal, CustomerNote
from .serializers import (
    CustomerSerializer, ContactSerializer, LeadSerializer, ActivitySerializer,
    DealSerializer, DealStageSerializer, CustomerNoteSerializer,
)


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['name', 'company', 'email', 'code']
    filterset_fields = ['is_active', 'industry']
    ordering_fields = ['name', 'created_at']

    @action(detail=True, methods=['get', 'post'], url_path='notes')
    def notes(self, request, pk=None):
        customer = self.get_object()
        if request.method == 'POST':
            serializer = CustomerNoteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(customer=customer, created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        qs = customer.notes.select_related('created_by').all()
        return Response(CustomerNoteSerializer(qs, many=True).data)


class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.select_related('customer').all()
    serializer_class = ContactSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'email', 'customer__name']
    filterset_fields = ['customer', 'is_primary']


class LeadViewSet(viewsets.ModelViewSet):
    queryset = Lead.objects.select_related('assigned_to', 'customer').all()
    serializer_class = LeadSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['name', 'company', 'email']
    filterset_fields = ['status', 'source', 'assigned_to']
    ordering_fields = ['created_at', 'estimated_value']

    @action(detail=True, methods=['get', 'post'], url_path='notes')
    def notes(self, request, pk=None):
        lead = self.get_object()
        if request.method == 'POST':
            serializer = CustomerNoteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(lead=lead, created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        qs = lead.note_entries.select_related('created_by').all()
        return Response(CustomerNoteSerializer(qs, many=True).data)


class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.select_related('user', 'lead', 'customer').all()
    serializer_class = ActivitySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['summary', 'body']
    filterset_fields = ['type', 'lead', 'customer']


class DealViewSet(viewsets.ModelViewSet):
    queryset = Deal.objects.select_related('customer', 'lead', 'assigned_to').all()
    serializer_class = DealSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['title']
    filterset_fields = ['stage', 'customer', 'lead', 'assigned_to']
    ordering_fields = ['created_at', 'value', 'expected_close']

    @action(detail=True, methods=['patch'], url_path='stage')
    def update_stage(self, request, pk=None):
        deal = self.get_object()
        serializer = DealStageSerializer(deal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(DealSerializer(deal).data)

    @action(detail=False, methods=['get'], url_path='pipeline-stats')
    def pipeline_stats(self, request):
        by_stage = {
            row['stage']: {'count': row['count'], 'value': float(row['total'] or 0)}
            for row in Deal.objects.values('stage').annotate(count=Count('id'), total=Sum('value'))
        }
        for stage_key, _ in Deal.STAGE_CHOICES:
            by_stage.setdefault(stage_key, {'count': 0, 'value': 0.0})

        won_count = by_stage['won']['count']
        lost_count = by_stage['lost']['count']
        decided = won_count + lost_count
        win_rate = round((won_count / decided) * 100, 1) if decided else 0.0

        total_pipeline_value = Deal.objects.exclude(stage='lost').aggregate(
            t=Sum('value')
        )['t'] or Decimal('0')

        return Response({
            'by_stage': by_stage,
            'total_pipeline_value': float(total_pipeline_value),
            'deals_won': by_stage['won'],
            'deals_lost': by_stage['lost'],
            'win_rate': win_rate,
        })


class CustomerNoteViewSet(viewsets.ModelViewSet):
    queryset = CustomerNote.objects.select_related('customer', 'lead', 'created_by').all()
    serializer_class = CustomerNoteSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filterset_fields = ['customer', 'lead', 'note_type']
    filter_backends = [DjangoFilterBackend]
