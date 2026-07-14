from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    SupplierViewSet, PurchaseOrderViewSet, PurchaseOrderItemViewSet,
    GoodsReceiptViewSet, BillViewSet, ProcurementDashboardView,
)

app_name = 'procurement'
router = DefaultRouter()
router.register('suppliers', SupplierViewSet, basename='supplier')
router.register('purchase-orders', PurchaseOrderViewSet, basename='purchase-order')
router.register('purchase-order-items', PurchaseOrderItemViewSet, basename='purchase-order-item')
router.register('goods-receipts', GoodsReceiptViewSet, basename='goods-receipt')
router.register('bills', BillViewSet, basename='bill')

urlpatterns = [
    path('dashboard/', ProcurementDashboardView.as_view(), name='procurement-dashboard'),
] + router.urls
