from rest_framework.routers import DefaultRouter
from .views import QuotationViewSet, QuotationItemViewSet, SalesOrderViewSet

app_name = 'sales'
router = DefaultRouter()
router.register('quotations', QuotationViewSet, basename='quotation')
router.register('quotation-items', QuotationItemViewSet, basename='quotation-item')
router.register('orders', SalesOrderViewSet, basename='sales-order')

urlpatterns = router.urls
