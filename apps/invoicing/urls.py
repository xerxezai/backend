from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    InvoiceViewSet, InvoiceItemViewSet, PaymentViewSet, InvoicingDashboardView,
    RecurringInvoiceViewSet, CreditNoteViewSet, InvoicingReportsView, InvoicingReportsExportView,
)

app_name = 'invoicing'
router = DefaultRouter()
router.register('invoices', InvoiceViewSet, basename='invoice')
router.register('invoice-items', InvoiceItemViewSet, basename='invoice-item')
router.register('payments', PaymentViewSet, basename='payment')
router.register('recurring-invoices', RecurringInvoiceViewSet, basename='recurring-invoice')
router.register('credit-notes', CreditNoteViewSet, basename='credit-note')

urlpatterns = [
    path('dashboard/', InvoicingDashboardView.as_view(), name='invoicing-dashboard'),
    path('reports/', InvoicingReportsView.as_view(), name='invoicing-reports'),
    path('reports/export-csv/', InvoicingReportsExportView.as_view(), name='invoicing-reports-export'),
] + router.urls
