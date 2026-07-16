import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Count
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.mixins import ProtectedDestroyMixin
from .models import Customer, Contact, Lead, Activity, Deal, CustomerNote
from .serializers import (
    CustomerSerializer, ContactSerializer, LeadSerializer, ActivitySerializer,
    DealSerializer, DealStageSerializer, CustomerNoteSerializer, _gen_code,
)


class CustomerViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['name', 'company', 'email', 'code']
    filterset_fields = ['is_active', 'industry']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        active = self.request.query_params.get('active')
        if active in ('true', 'false'):
            qs = qs.filter(is_active=(active == 'true'))
        tag = self.request.query_params.get('tag')
        if tag:
            qs = qs.filter(tags__contains=[tag])
        return qs

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

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        customer = self.get_object()
        deals = Deal.objects.filter(customer=customer).select_related('assigned_to')
        activities = Activity.objects.filter(customer=customer).select_related('user')
        notes = customer.notes.select_related('created_by').all()
        return Response({
            'customer': CustomerSerializer(customer).data,
            'deals': DealSerializer(deals, many=True).data,
            'activities': ActivitySerializer(activities, many=True).data,
            'notes': CustomerNoteSerializer(notes, many=True).data,
        })

    @action(detail=False, methods=['post'], url_path='bulk-import')
    def bulk_import(self, request):
        """CSV columns: name, company, email, phone, industry, source, city, country, tags
        (tags is a semicolon-separated list, e.g. "VIP;Prospect"). Only 'name' is required."""
        f = request.FILES.get('file')
        if not f:
            return Response({'detail': 'No file uploaded. Send it as multipart field "file".'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            text = f.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response({'detail': 'File must be UTF-8 encoded CSV.'}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(io.StringIO(text))
        to_create, row_numbers, errors = [], [], []
        valid_sources = {s for s, _ in Customer.SOURCE}

        # _gen_code() re-queries count()+exists() per call, which is both a per-row
        # DB round trip and, if called repeatedly before any row is actually saved
        # (as a single bulk_create requires), would hand out the same duplicate code
        # to every row. Generate all codes for this import up front, tracked in memory.
        next_n = Customer.objects.count()
        existing_codes = set(Customer.objects.values_list('code', flat=True))

        def next_code():
            nonlocal next_n
            while True:
                next_n += 1
                code = f"CUST{str(next_n).zfill(4)}"
                if code not in existing_codes:
                    existing_codes.add(code)
                    return code

        for i, row in enumerate(reader, start=2):
            row = {(k or '').strip(): (v or '').strip() for k, v in row.items()}
            name = row.get('name')
            if not name:
                errors.append({'row': i, 'error': 'Missing "name".'})
                continue
            try:
                source = row.get('source') or ''
                if source and source not in valid_sources:
                    errors.append({'row': i, 'error': f'Invalid source "{source}".'})
                    continue
                tags = [t.strip() for t in (row.get('tags') or '').split(';') if t.strip()]
                customer = Customer(
                    name=name, company=row.get('company', ''), email=row.get('email', ''),
                    phone=row.get('phone', ''), industry=row.get('industry', ''),
                    source=source, city=row.get('city', ''), country=row.get('country', ''),
                    tags=tags, code=next_code(),
                )
                customer.full_clean()
                to_create.append(customer)
                row_numbers.append(i)
            except Exception as exc:
                errors.append({'row': i, 'error': str(exc)})

        with transaction.atomic():
            Customer.objects.bulk_create(to_create, batch_size=500)

        created = [
            {'row': row_i, 'id': c.id, 'name': c.name, 'code': c.code}
            for row_i, c in zip(row_numbers, to_create)
        ]
        return Response({'created_count': len(created), 'created': created, 'errors': errors}, status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        customers = self.get_queryset()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="customers-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Code', 'Name', 'Company', 'Email', 'Phone', 'Industry', 'Source', 'City', 'Country', 'Tags', 'Active'])
        for c in customers:
            writer.writerow([c.code, c.name, c.company, c.email, c.phone, c.industry, c.source, c.city, c.country, ';'.join(c.tags or []), c.is_active])
        return response


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
    filterset_fields = ['status', 'source', 'score', 'assigned_to']
    ordering_fields = ['created_at', 'estimated_value', 'follow_up_date']

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

    @action(detail=True, methods=['post'], url_path='convert')
    def convert(self, request, pk=None):
        """Converts a lead into a Customer, linking the lead to the new/existing customer."""
        lead = self.get_object()
        if lead.customer_id:
            return Response(
                {'detail': f'Already converted to customer {lead.customer.code}.', 'customer': CustomerSerializer(lead.customer).data},
                status=status.HTTP_400_BAD_REQUEST,
            )
        customer = Customer.objects.create(
            code=_gen_code(Customer, 'CUST'),
            name=lead.name, company=lead.company, email=lead.email, phone=lead.phone,
            source=lead.source if lead.source in dict(Customer.SOURCE) else '',
        )
        lead.customer = customer
        lead.status = 'won'
        lead.save(update_fields=['customer', 'status'])
        return Response({'customer': CustomerSerializer(customer).data, 'lead': LeadSerializer(lead).data}, status=status.HTTP_201_CREATED)


class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.select_related('user', 'lead', 'customer').all()
    serializer_class = ActivitySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['summary', 'body']
    filterset_fields = {
        'type': ['exact'],
        'lead': ['exact'],
        'customer': ['exact'],
        'completed': ['exact'],
        'due_date': ['exact', 'gte', 'lte'],
    }

    @action(detail=True, methods=['put', 'patch'], url_path='complete')
    def complete(self, request, pk=None):
        activity = self.get_object()
        activity.completed = True
        activity.save(update_fields=['completed'])
        return Response(ActivitySerializer(activity).data)

    @action(detail=False, methods=['get'], url_path='overdue')
    def overdue(self, request):
        today = timezone.now().date()
        qs = self.get_queryset().filter(due_date__lt=today, completed=False)
        return Response(ActivitySerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='today')
    def today(self, request):
        today = timezone.now().date()
        qs = self.get_queryset().filter(due_date=today)
        return Response(ActivitySerializer(qs, many=True).data)


class DealViewSet(viewsets.ModelViewSet):
    queryset = Deal.objects.select_related('customer', 'lead', 'assigned_to').all()
    serializer_class = DealSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['title']
    filterset_fields = {
        'stage': ['exact'],
        'customer': ['exact'],
        'lead': ['exact'],
        'assigned_to': ['exact'],
        'expected_close': ['exact', 'gte', 'lte'],
    }
    ordering_fields = ['created_at', 'value', 'expected_close']

    def get_queryset(self):
        qs = super().get_queryset()
        outcome = self.request.query_params.get('outcome')
        if outcome == 'won':
            qs = qs.filter(stage='won')
        elif outcome == 'lost':
            qs = qs.filter(stage='lost')
        elif outcome == 'pending':
            qs = qs.exclude(stage__in=['won', 'lost'])
        return qs

    @action(detail=True, methods=['put', 'patch'], url_path='stage')
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


class PipelineView(APIView):
    """Deals grouped by stage — GET /api/v1/crm/pipeline/. The existing Kanban board
    (CRMPipeline.tsx) already groups client-side from GET crm/deals/; this endpoint
    covers the task's literal requirement for API consumers that want it pre-grouped."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        deals = Deal.objects.select_related('customer', 'lead', 'assigned_to').all()
        grouped: dict = {key: [] for key, _ in Deal.STAGE_CHOICES}
        for d in deals:
            grouped.setdefault(d.stage, []).append(DealSerializer(d).data)
        return Response(grouped)


class CustomerNoteViewSet(viewsets.ModelViewSet):
    queryset = CustomerNote.objects.select_related('customer', 'lead', 'created_by').all()
    serializer_class = CustomerNoteSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filterset_fields = ['customer', 'lead', 'note_type']
    filter_backends = [DjangoFilterBackend]


class CRMDashboardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)

        total_customers = Customer.objects.count()
        total_leads = Lead.objects.count()
        total_deals_value = float(Deal.objects.exclude(stage='lost').aggregate(t=Sum('value'))['t'] or 0)

        won = Lead.objects.filter(status='won').count()
        decided = Lead.objects.filter(status__in=['won', 'lost']).count()
        leads_conversion_rate = round((won / decided) * 100, 1) if decided else 0.0

        top_5 = list(
            Deal.objects.exclude(customer__isnull=True).values('customer_id', 'customer__name')
            .annotate(total=Sum('value')).order_by('-total')[:5]
        )
        top_5_customers_by_deal_value = [
            {'customer_id': r['customer_id'], 'customer_name': r['customer__name'], 'value': float(r['total'] or 0)}
            for r in top_5
        ]

        month_starts = []
        y, m = month_start.year, month_start.month
        for _ in range(6):
            month_starts.append(month_start.__class__(y, m, 1))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        month_starts.reverse()
        monthly_deals_last_6_months = []
        for i, ms in enumerate(month_starts):
            if i + 1 < len(month_starts):
                me = month_starts[i + 1]
            else:
                ny, nm = (ms.year + 1, 1) if ms.month == 12 else (ms.year, ms.month + 1)
                me = ms.replace(year=ny, month=nm)
            agg = Deal.objects.filter(created_at__date__gte=ms, created_at__date__lt=me).aggregate(count=Count('id'), value=Sum('value'))
            monthly_deals_last_6_months.append({'month': ms.strftime('%b %Y'), 'count': agg['count'] or 0, 'value': float(agg['value'] or 0)})

        pipeline_value_by_stage = [
            {'stage': row['stage'], 'value': float(row['total'] or 0)}
            for row in Deal.objects.values('stage').annotate(total=Sum('value')).order_by('stage')
        ]

        activities_due_today = Activity.objects.filter(due_date=today).count()
        overdue_activities = Activity.objects.filter(due_date__lt=today, completed=False).count()

        return Response({
            'total_customers': total_customers,
            'total_leads': total_leads,
            'total_deals_value': total_deals_value,
            'leads_conversion_rate': leads_conversion_rate,
            'top_5_customers_by_deal_value': top_5_customers_by_deal_value,
            'monthly_deals_last_6_months': monthly_deals_last_6_months,
            'pipeline_value_by_stage': pipeline_value_by_stage,
            'activities_due_today': activities_due_today,
            'overdue_activities': overdue_activities,
        })
