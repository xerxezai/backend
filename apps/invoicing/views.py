import csv
from decimal import Decimal

from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
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

    @action(detail=True, methods=['put', 'post'], url_path='mark-paid')
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

    @action(detail=True, methods=['put', 'post'], url_path='send')
    def send(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status in ('paid', 'cancelled'):
            return Response(
                {'detail': f'Cannot send an invoice that is already {invoice.get_status_display().lower()}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invoice.status = 'sent'
        invoice.save(update_fields=['status'])
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
    queryset = Payment.objects.select_related('invoice', 'invoice__customer').all()
    serializer_class = PaymentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['invoice__number', 'invoice__customer__name', 'reference']
    filterset_fields = {
        'invoice': ['exact'],
        'method': ['exact'],
        'paid_at': ['exact', 'gte', 'lte'],
    }
    ordering_fields = ['paid_at', 'amount']

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

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        payments = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="payments-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Invoice', 'Customer', 'Amount', 'Method', 'Reference', 'Date', 'Notes'])
        for p in payments:
            writer.writerow([p.invoice.number, p.invoice.customer.name, p.amount, p.get_method_display(), p.reference, p.paid_at, p.notes])
        return response


class InvoicingDashboardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)

        total_invoiced = Invoice.objects.exclude(status='cancelled').aggregate(t=Sum('total'))['t'] or Decimal('0')
        total_paid = Payment.objects.aggregate(t=Sum('amount'))['t'] or Decimal('0')
        total_paid_this_month = Payment.objects.filter(paid_at__date__gte=month_start).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        outstanding = Invoice.objects.filter(status__in=['sent', 'partial', 'overdue']).aggregate(
            t=Sum('total')
        )['t'] or Decimal('0')
        outstanding -= Invoice.objects.filter(status__in=['sent', 'partial', 'overdue']).aggregate(
            p=Sum('amount_paid')
        )['p'] or Decimal('0')
        overdue_count = Invoice.objects.filter(due_date__lt=today).exclude(status__in=['paid', 'cancelled']).count()

        return Response({
            'total_invoiced': str(total_invoiced),
            'total_paid': str(total_paid),
            'total_paid_this_month': str(total_paid_this_month),
            'outstanding': str(outstanding),
            'overdue_count': overdue_count,
        })
