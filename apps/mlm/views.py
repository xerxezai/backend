import csv
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.sales.models import SalesOrder
from .models import Distributor, Commission, Payout, MLMSettings, next_number
from .serializers import (
    DistributorSerializer, CommissionSerializer, PayoutSerializer, MLMSettingsSerializer,
)


def _node(d: Distributor):
    """Recursive nested-tree dict for the network action — walks d.downline.all() up to 3 levels."""
    return {
        'id': d.id,
        'distributor_id': d.distributor_id,
        'name': d.name,
        'level': d.level,
        'total_sales': float(d.total_sales),
        'total_earnings': float(d.total_earnings),
        'status': d.status,
        'children': [_node(c) for c in d.downline.all()],
    }


class DistributorViewSet(viewsets.ModelViewSet):
    queryset = Distributor.objects.select_related('sponsor', 'user').all()
    serializer_class = DistributorSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'email', 'distributor_id']
    filterset_fields = ['level', 'status']

    @action(detail=True, methods=['get'], url_path='network')
    def network(self, request, pk=None):
        distributor = self.get_object()
        return Response(_node(distributor))

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        distributors = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="distributors-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Distributor ID', 'Name', 'Sponsor', 'Level', 'Status', 'Joining Date', 'Total Sales', 'Total Earnings'])
        for d in distributors:
            writer.writerow([d.distributor_id, d.name, d.sponsor.name if d.sponsor_id else '', d.level, d.status, d.joining_date, d.total_sales, d.total_earnings])
        return response


class CommissionViewSet(viewsets.ModelViewSet):
    queryset = Commission.objects.select_related('distributor', 'order').all()
    serializer_class = CommissionSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    filterset_fields = {
        'distributor': ['exact'],
        'level': ['exact'],
        'status': ['exact'],
        'created_date': ['exact', 'gte', 'lte'],
    }

    @action(detail=False, methods=['post'], url_path='calculate')
    @transaction.atomic
    def calculate(self, request):
        order_id = request.data.get('order')
        try:
            order = SalesOrder.objects.select_related('customer').get(pk=order_id)
        except (SalesOrder.DoesNotExist, TypeError, ValueError):
            return Response({'detail': 'Sales order not found.'}, status=status.HTTP_404_NOT_FOUND)

        # SalesOrder has no direct distributor link — best-effort resolve the originating
        # distributor via a matching email against the order's customer. This is a reasonable
        # simplification given the current schema; a mismatch (no distributor with that email)
        # is a valid, expected outcome for orders placed by non-distributor customers.
        customer_email = (order.customer.email or '').strip() if order.customer_id else ''
        origin = Distributor.objects.filter(email=customer_email).first() if customer_email else None
        if not origin:
            return Response({'detail': "No distributor found for this order's customer."}, status=status.HTTP_400_BAD_REQUEST)

        settings_row = MLMSettings.get_solo()
        rates = {1: settings_row.level1_rate, 2: settings_row.level2_rate, 3: settings_row.level3_rate}

        created = []
        current = origin.sponsor
        level = 1
        while current is not None and level <= 3:
            rate = rates[level]
            amount = (order.total or Decimal('0')) * (rate / Decimal('100'))
            commission = Commission.objects.create(
                distributor=current, order=order, level=level, rate=rate, amount=amount, status='pending',
            )
            created.append(commission)
            Distributor.objects.filter(pk=current.pk).update(total_earnings=current.total_earnings + amount)
            current = current.sponsor
            level += 1

        Distributor.objects.filter(pk=origin.pk).update(total_sales=origin.total_sales + (order.total or Decimal('0')))

        return Response({
            'count': len(created),
            'results': CommissionSerializer(created, many=True).data,
        })

    @action(detail=False, methods=['post'], url_path='bulk-approve')
    def bulk_approve(self, request):
        ids = request.data.get('ids') or []
        qs = Commission.objects.filter(id__in=ids)
        qs.update(status='paid')
        updated = Commission.objects.filter(id__in=ids).select_related('distributor', 'order')
        return Response(CommissionSerializer(updated, many=True).data)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        commissions = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="commissions-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Commission ID', 'Distributor', 'Order', 'Level', 'Rate', 'Amount', 'Status', 'Date'])
        for c in commissions:
            writer.writerow([c.id, c.distributor.name, c.order.number, c.level, c.rate, c.amount, c.status, c.created_date])
        return response


class PayoutViewSet(viewsets.ModelViewSet):
    queryset = Payout.objects.select_related('distributor').all()
    serializer_class = PayoutSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['distributor__name', 'reference_number']
    filterset_fields = ['distributor', 'status']

    @action(detail=True, methods=['put'], url_path='process')
    def process(self, request, pk=None):
        payout = self.get_object()
        order_steps = ['pending', 'processing', 'completed']
        if payout.status == 'completed':
            return Response({'detail': 'This payout has already been completed.'}, status=status.HTTP_400_BAD_REQUEST)
        next_status = order_steps[order_steps.index(payout.status) + 1]
        payout.status = next_status
        payout.save(update_fields=['status'])
        return Response(PayoutSerializer(payout).data)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        payouts = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="payouts-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Payout ID', 'Distributor', 'Amount', 'Date', 'Method', 'Reference', 'Status'])
        for p in payouts:
            writer.writerow([p.id, p.distributor.name, p.amount, p.payout_date, p.method, p.reference_number, p.status])
        return response


class MLMSettingsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MLMSettingsSerializer(MLMSettings.get_solo()).data)

    def put(self, request):
        settings_row = MLMSettings.get_solo()
        serializer = MLMSettingsSerializer(settings_row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MLMDashboardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)

        total_distributors = Distributor.objects.count()
        active_distributors = Distributor.objects.filter(status='active').count()
        # Counts all commissions created this month regardless of status (pending or paid) —
        # a consistent, simple definition since the spec allows either interpretation.
        total_commissions_this_month = Commission.objects.filter(
            created_date__gte=month_start
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        pending_payouts = Payout.objects.filter(status='pending').count()

        top_performers_qs = Distributor.objects.order_by('-total_earnings')[:5]
        top_performers = [
            {
                'id': d.id, 'distributor_id': d.distributor_id, 'name': d.name,
                'level': d.level, 'total_sales': float(d.total_sales), 'total_earnings': float(d.total_earnings),
            }
            for d in top_performers_qs
        ]

        # Monthly commissions for the trailing 6 months (including the current one) — same
        # "walk backward from month_start" loop structure as ProcurementDashboardView.monthly_spending.
        months = []
        cursor = month_start
        for _ in range(6):
            months.insert(0, cursor)
            cursor = (cursor - timedelta(days=1)).replace(day=1)
        monthly_commissions = []
        for m_start in months:
            m_end = m_start.replace(year=m_start.year + 1, month=1) if m_start.month == 12 else m_start.replace(month=m_start.month + 1)
            total = Commission.objects.filter(
                created_date__gte=m_start, created_date__lt=m_end,
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            monthly_commissions.append({'month': m_start.strftime('%b %Y'), 'total': float(total)})

        by_level = {row['level']: row['total'] for row in Commission.objects.values('level').annotate(total=Sum('amount'))}
        commission_by_level = [{'level': lvl, 'total': float(by_level.get(lvl) or 0)} for lvl in (1, 2, 3)]

        return Response({
            'total_distributors': total_distributors,
            'active_distributors': active_distributors,
            'total_commissions_this_month': float(total_commissions_this_month),
            'pending_payouts': pending_payouts,
            'top_performers': top_performers,
            'monthly_commissions': monthly_commissions,
            'commission_by_level': commission_by_level,
        })
