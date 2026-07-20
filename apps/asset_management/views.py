import csv
from decimal import Decimal
from io import BytesIO

import qrcode
from django.core.files.base import ContentFile
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
from .models import Asset, MaintenanceRecord, AssetDepreciation
from .serializers import AssetSerializer, MaintenanceRecordSerializer, AssetDepreciationSerializer


def sync_depreciation_for_asset(asset: Asset):
    """Computes/refreshes one straight-line AssetDepreciation row per year from the asset's
    purchase year through the current year — idempotent (get_or_create + update-if-stale) so
    repeated GETs never duplicate rows, and a changed depreciation_rate/purchase_cost is
    reflected on the next read rather than needing a manual recalculation step."""
    if not asset.purchase_date or asset.depreciation_rate <= 0:
        return
    opening = asset.purchase_cost
    rate = asset.depreciation_rate / Decimal('100')
    current_year = timezone.now().year
    for year in range(asset.purchase_date.year, current_year + 1):
        depreciation_amount = (opening * rate).quantize(Decimal('0.01'))
        closing = opening - depreciation_amount
        entry, created = AssetDepreciation.objects.get_or_create(
            asset=asset, year=year,
            defaults={'opening_value': opening, 'depreciation_amount': depreciation_amount, 'closing_value': closing},
        )
        if not created and (entry.opening_value != opening or entry.depreciation_amount != depreciation_amount):
            entry.opening_value = opening
            entry.depreciation_amount = depreciation_amount
            entry.closing_value = closing
            entry.save(update_fields=['opening_value', 'depreciation_amount', 'closing_value'])
        opening = closing


class AssetViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Asset.objects.select_related('assigned_to').all()
    serializer_class = AssetSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['name', 'asset_code', 'location', 'department']
    filterset_fields = ['category', 'status', 'assigned_to']
    ordering_fields = ['purchase_date', 'purchase_cost', 'next_maintenance']

    @action(detail=True, methods=['get', 'post'], url_path='maintenance')
    def maintenance(self, request, pk=None):
        asset = self.get_object()
        if request.method == 'POST':
            ser = MaintenanceRecordSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            record = ser.save(asset=asset, created_by=request.user, company=asset.company)
            # A logged maintenance visit updates the asset's own maintenance-tracking fields —
            # single source of truth instead of the frontend having to keep both in sync.
            asset.last_maintenance = record.date
            if record.next_due:
                asset.next_maintenance = record.next_due
            if asset.status == 'under_maintenance':
                asset.status = 'active'
            asset.save(update_fields=['last_maintenance', 'next_maintenance', 'status'])
            return Response(ser.data, status=status.HTTP_201_CREATED)
        qs = asset.maintenance_records.select_related('created_by').all()
        return Response(MaintenanceRecordSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'], url_path='depreciation')
    def depreciation(self, request, pk=None):
        asset = self.get_object()
        sync_depreciation_for_asset(asset)
        qs = asset.depreciation_entries.all()
        return Response(AssetDepreciationSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='generate-qr')
    def generate_qr(self, request, pk=None):
        asset = self.get_object()
        payload = (request.data.get('data') or '').strip() or asset.asset_code
        img = qrcode.make(payload)
        buf = BytesIO()
        img.save(buf, format='PNG')
        asset.qr_code = payload
        asset.qr_code_image.save(f'{asset.asset_code}.png', ContentFile(buf.getvalue()), save=False)
        asset.save(update_fields=['qr_code', 'qr_code_image'])
        return Response(AssetSerializer(asset, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        assets = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="assets-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Code', 'Name', 'Category', 'Status', 'Location', 'Assigned To', 'Purchase Cost', 'Current Value', 'Next Maintenance'])
        for a in assets:
            writer.writerow([a.asset_code, a.name, a.category, a.status, a.location, a.assigned_to.get_full_name() if a.assigned_to_id else '', a.purchase_cost, a.current_value or '', a.next_maintenance or ''])
        return response

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        today = timezone.now().date()
        in_30_days = today + timezone.timedelta(days=30)
        month_start = today.replace(day=1)
        qs = self.get_queryset()
        total_value = qs.aggregate(t=Sum('current_value'))['t']
        if total_value is None:
            total_value = qs.aggregate(t=Sum('purchase_cost'))['t'] or Decimal('0')
        maintenance_cost_this_month = self.company_scope(MaintenanceRecord.objects.all()).filter(
            date__gte=month_start, date__lte=today,
        ).aggregate(t=Sum('cost'))['t'] or Decimal('0')
        return Response({
            'total_assets': qs.count(),
            'active_assets': qs.filter(status='active').count(),
            'under_maintenance': qs.filter(status='under_maintenance').count(),
            'due_for_maintenance': qs.filter(next_maintenance__isnull=False, next_maintenance__lte=in_30_days, next_maintenance__gte=today).count(),
            'total_asset_value': float(total_value),
            'maintenance_cost_this_month': float(maintenance_cost_this_month),
        })


class MaintenanceRecordViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = MaintenanceRecord.objects.select_related('asset', 'created_by').all()
    serializer_class = MaintenanceRecordSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['asset', 'maintenance_type']


class AssetDepreciationViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AssetDepreciation.objects.select_related('asset').all()
    serializer_class = AssetDepreciationSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['asset', 'year']
