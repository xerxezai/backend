import csv

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.rbac.utils import filter_queryset_by_role
from apps.rbac.mixins import RBACScopedMixin
from .models import Shipment, TrackingUpdate, Delivery, Warehouse
from .serializers import ShipmentSerializer, TrackingUpdateSerializer, DeliverySerializer, WarehouseSerializer


def generate_delivery_for_shipment(shipment, user=None):
    """Books one Delivery record the first time a Shipment reaches 'delivered', idempotent on
    the shipment FK so re-marking an already-delivered shipment (or a retried request) never
    creates a duplicate — mirrors apps.sales.views.generate_stock_out_for_order."""
    if Delivery.objects.filter(shipment=shipment).exists():
        return
    delivered_by = ''
    if user and getattr(user, 'is_authenticated', False):
        delivered_by = user.get_full_name() or user.username
    Delivery.objects.create(
        shipment=shipment,
        delivery_date=shipment.actual_delivery or timezone.now().date(),
        delivered_by=delivered_by,
        status='delivered',
        notes='Auto-recorded when the shipment was marked delivered.',
        # The delivery belongs to whoever owns the shipment, so the same user keeps
        # seeing it on the Deliveries page under the own-data-only rule.
        created_by=shipment.created_by,
    )


class ShipmentViewSet(RBACScopedMixin, viewsets.ModelViewSet):
    rbac_module = 'logistics'
    queryset = Shipment.objects.select_related('customer', 'sales_order').prefetch_related('tracking_updates').all()
    serializer_class = ShipmentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['tracking_number', 'shipment_number', 'customer__name', 'carrier']
    filterset_fields = ['status', 'customer']
    ordering_fields = ['created_at', 'estimated_delivery']

    @action(detail=True, methods=['put'], url_path='status')
    def status_update(self, request, pk=None):
        self._rbac_block_read_only()
        shipment = self.get_object()
        new_status = request.data.get('status')
        valid_statuses = dict(Shipment.STATUS)
        if new_status not in valid_statuses:
            return Response({'detail': f'Invalid status. Must be one of {list(valid_statuses)}.'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        shipment.status = new_status
        if new_status == 'delivered':
            if not shipment.actual_delivery:
                shipment.actual_delivery = now.date()
            if not shipment.delivered_at:
                shipment.delivered_at = now
        shipment.save()

        TrackingUpdate.objects.create(
            shipment=shipment, status=new_status, location='',
            description=f'Status changed to {valid_statuses[new_status]}', occurred_at=now,
        )

        if new_status == 'delivered':
            generate_delivery_for_shipment(shipment, user=request.user)

        return Response(ShipmentSerializer(shipment).data)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        shipments = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="shipments-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Shipment Number', 'Tracking Number', 'Customer', 'Carrier', 'Origin', 'Destination', 'Status', 'Estimated Delivery', 'Actual Delivery'])
        for s in shipments:
            writer.writerow([s.shipment_number, s.tracking_number, s.customer.name, s.carrier, s.origin, s.destination, s.status, s.estimated_delivery, s.actual_delivery])
        return response


class TrackingUpdateViewSet(RBACScopedMixin, viewsets.ModelViewSet):
    rbac_module = 'logistics'
    rbac_user_field = 'shipment__created_by'   # tracking rows are owned via their shipment
    rbac_stamp_created_by = False
    queryset = TrackingUpdate.objects.select_related('shipment').all()
    serializer_class = TrackingUpdateSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['shipment']
    ordering_fields = ['occurred_at']


class DeliveryViewSet(RBACScopedMixin, viewsets.ModelViewSet):
    rbac_module = 'logistics'
    queryset = Delivery.objects.select_related('shipment', 'shipment__customer').all()
    serializer_class = DeliverySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['shipment', 'status']
    ordering_fields = ['delivery_date']


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'location']
    filterset_fields = ['is_active']

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        warehouses = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="warehouses-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Location', 'Capacity', 'Manager', 'Active'])
        for w in warehouses:
            writer.writerow([w.name, w.location, w.capacity, w.manager, w.is_active])
        return response


class LogisticsDashboardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()

        shipments_qs = filter_queryset_by_role(Shipment.objects.all(), request.user, 'logistics')

        total_shipments = shipments_qs.count()
        in_transit = shipments_qs.filter(status='in_transit').count()
        pending = shipments_qs.filter(status='pending').count()
        delivered_today = shipments_qs.filter(status='delivered').filter(
            Q(actual_delivery=today) | Q(delivered_at__date=today)
        ).count()

        delivered_with_dates = shipments_qs.filter(
            status='delivered', estimated_delivery__isnull=False, actual_delivery__isnull=False,
        )
        denom = delivered_with_dates.count()
        on_time_count = sum(1 for s in delivered_with_dates if s.actual_delivery <= s.estimated_delivery)
        on_time_rate = round((on_time_count / denom) * 100, 1) if denom else 0.0

        recent_shipments = shipments_qs.select_related('customer').order_by('-created_at')[:8]

        shipments_by_status = [
            {'status': s_key, 'count': shipments_qs.filter(status=s_key).count()}
            for s_key, _label in Shipment.STATUS
        ]

        return Response({
            'total_shipments': total_shipments,
            'in_transit': in_transit,
            'delivered_today': delivered_today,
            'pending': pending,
            'on_time_rate': float(on_time_rate),
            'recent_shipments': ShipmentSerializer(recent_shipments, many=True).data,
            'shipments_by_status': shipments_by_status,
        })
