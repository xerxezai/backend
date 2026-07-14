from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import InvoiceViewSet, InvoiceItemViewSet, PaymentViewSet, InvoicingDashboardView

app_name = 'invoicing'
router = DefaultRouter()
router.register('invoices', InvoiceViewSet, basename='invoice')
router.register('invoice-items', InvoiceItemViewSet, basename='invoice-item')
router.register('payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path('dashboard/', InvoicingDashboardView.as_view(), name='invoicing-dashboard'),
] + router.urls
