from rest_framework import viewsets, filters
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Shipment, TrackingUpdate
from .serializers import ShipmentSerializer, TrackingUpdateSerializer


class ShipmentViewSet(viewsets.ModelViewSet):
    queryset = Shipment.objects.select_related('customer', 'sales_order').prefetch_related('tracking_updates').all()
    serializer_class = ShipmentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['tracking_number', 'customer__name', 'carrier']
    filterset_fields = ['status', 'customer']
    ordering_fields = ['created_at', 'estimated_delivery']


class TrackingUpdateViewSet(viewsets.ModelViewSet):
    queryset = TrackingUpdate.objects.select_related('shipment').all()
    serializer_class = TrackingUpdateSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['shipment']
    ordering_fields = ['occurred_at']
