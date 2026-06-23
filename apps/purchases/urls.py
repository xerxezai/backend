from rest_framework.routers import DefaultRouter
from .views import VendorViewSet, PurchaseOrderViewSet, PurchaseOrderItemViewSet

app_name = 'purchases'
router = DefaultRouter()
router.register('vendors', VendorViewSet, basename='vendor')
router.register('orders', PurchaseOrderViewSet, basename='purchase-order')
router.register('order-items', PurchaseOrderItemViewSet, basename='purchase-order-item')

urlpatterns = router.urls
