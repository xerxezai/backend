from rest_framework.routers import DefaultRouter
from .views import InvoiceViewSet, InvoiceItemViewSet, PaymentViewSet

app_name = 'invoicing'
router = DefaultRouter()
router.register('invoices', InvoiceViewSet, basename='invoice')
router.register('invoice-items', InvoiceItemViewSet, basename='invoice-item')
router.register('payments', PaymentViewSet, basename='payment')

urlpatterns = router.urls
