import csv
from decimal import Decimal

from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Invoice, InvoiceItem, Payment
from .serializers import InvoiceSerializer, InvoiceItemSerializer, PaymentSerializer


def sync_invoice_payment_status(invoice: Invoice):
    """Single source of truth for amount_paid/status — always derived from the Payment ledger,
    never set directly, so the two can't drift out of sync."""
    total_paid = invoice.payments.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    invoice.amount_paid = total_paid
    if total_paid >= invoice.total and invoice.total > 0:
        invoice.status = 'paid'
    elif total_paid > 0:
        invoice.status = 'partial'
    elif invoice.status in ('paid', 'partial'):
        invoice.status = 'sent'
    invoice.save(update_fields=['amount_paid', 'status'])


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related('customer', 'sales_order').prefetch_related('items').all()
    serializer_class = InvoiceSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['number', 'customer__name']
    filterset_fields = {
        'status': ['exact'],
        'customer': ['exact'],
        'issue_date': ['exact', 'gte', 'lte'],
        'due_date': ['exact', 'gte', 'lte'],
    }
    ordering_fields = ['issue_date', 'due_date', 'total']

    @action(detail=True, methods=['post'], url_path='mark-paid')
    def mark_paid(self, request, pk=None):
        invoice = self.get_object()
        balance = invoice.balance
        if balance > 0:
            Payment.objects.create(
                invoice=invoice, amount=balance, method='other',
                reference='Marked as paid', paid_at=timezone.now(),
                notes='Full balance settled via "Mark as Paid".',
            )
        sync_invoice_payment_status(invoice)
        invoice.refresh_from_db()
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        invoices = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="invoices-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Number', 'Customer', 'Issue Date', 'Due Date', 'Status', 'Subtotal', 'Tax', 'Total', 'Amount Paid', 'Balance'])
        for inv in invoices:
            writer.writerow([inv.number, inv.customer.name, inv.issue_date, inv.due_date, inv.status, inv.subtotal, inv.tax, inv.total, inv.amount_paid, inv.balance])
        return response


class InvoiceItemViewSet(viewsets.ModelViewSet):
    queryset = InvoiceItem.objects.select_related('invoice', 'product').all()
    serializer_class = InvoiceItemSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['invoice']


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('invoice').all()
    serializer_class = PaymentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['invoice', 'method']
    ordering_fields = ['paid_at']

    def perform_create(self, serializer):
        payment = serializer.save()
        sync_invoice_payment_status(payment.invoice)

    def perform_update(self, serializer):
        payment = serializer.save()
        sync_invoice_payment_status(payment.invoice)

    def perform_destroy(self, instance):
        invoice = instance.invoice
        instance.delete()
        sync_invoice_payment_status(invoice)
