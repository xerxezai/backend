from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ShipmentViewSet, TrackingUpdateViewSet, DeliveryViewSet, WarehouseViewSet,
    LogisticsDashboardView,
)

app_name = 'logistics'
router = DefaultRouter()
router.register('shipments', ShipmentViewSet, basename='shipment')
router.register('tracking', TrackingUpdateViewSet, basename='tracking-update')
router.register('deliveries', DeliveryViewSet, basename='delivery')
router.register('warehouses', WarehouseViewSet, basename='warehouse')

urlpatterns = [
    path('dashboard/', LogisticsDashboardView.as_view(), name='logistics-dashboard'),
] + router.urls
