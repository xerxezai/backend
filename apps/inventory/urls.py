from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    ProductCategoryViewSet, ProductViewSet, WarehouseViewSet, StockMovementViewSet,
    StockTransferView, InventoryDashboardView, StockValuationReportView, ProductsExportCSVView,
)

app_name = 'inventory'
router = DefaultRouter()
router.register('categories', ProductCategoryViewSet, basename='product-category')
router.register('products', ProductViewSet, basename='product')
router.register('warehouses', WarehouseViewSet, basename='warehouse')
router.register('stock-movements', StockMovementViewSet, basename='stock-movement')

urlpatterns = [
    path('stock-transfer/', StockTransferView.as_view(), name='stock-transfer'),
    path('dashboard/', InventoryDashboardView.as_view(), name='inventory-dashboard'),
    path('reports/valuation/', StockValuationReportView.as_view(), name='stock-valuation'),
    path('reports/export-csv/', ProductsExportCSVView.as_view(), name='products-export-csv'),
] + router.urls
