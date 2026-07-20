import csv
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.mixins import ProtectedDestroyMixin
from apps.invoicing.models import Invoice
from apps.procurement.models import PurchaseOrder, Bill
from apps.rbac.utils import filter_queryset_by_role
from apps.rbac.mixins import RBACScopedMixin

from .models import Account, JournalEntry, JournalLine, Expense, next_number
from .serializers import AccountSerializer, JournalEntrySerializer, JournalLineSerializer, ExpenseSerializer


class AccountViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'code']
    filterset_fields = ['type', 'is_active']


class JournalEntryViewSet(RBACScopedMixin, viewsets.ModelViewSet):
    rbac_module = 'accounting'
    queryset = JournalEntry.objects.prefetch_related('lines__account').all()
    serializer_class = JournalEntrySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['number', 'description', 'reference']
    filterset_fields = ['posted']
    ordering_fields = ['date', 'created_at']


class JournalLineViewSet(RBACScopedMixin, viewsets.ModelViewSet):
    rbac_module = 'accounting'
    rbac_user_field = 'entry__created_by'   # lines are owned via their journal entry
    rbac_stamp_created_by = False
    queryset = JournalLine.objects.select_related('entry', 'account').all()
    serializer_class = JournalLineSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['entry', 'account']


class ExpenseViewSet(RBACScopedMixin, viewsets.ModelViewSet):
    rbac_module = 'accounting'
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['expense_number', 'category', 'description', 'paid_by']
    filterset_fields = {
        'status': ['exact'],
        'category': ['exact'],
        'date': ['exact', 'gte', 'lte'],
    }

    def perform_create(self, serializer):
        self._rbac_block_read_only()
        serializer.save(expense_number=next_number(Expense, 'expense_number', 'EXP'), created_by=self.request.user)

    @action(detail=True, methods=['put'], url_path='approve')
    def approve(self, request, pk=None):
        self._rbac_block_read_only()
        expense = self.get_object()
        new_status = request.data.get('status') or 'approved'
        if new_status not in ('approved', 'rejected'):
            return Response({'detail': 'status must be "approved" or "rejected".'}, status=status.HTTP_400_BAD_REQUEST)
        expense.status = new_status
        expense.save(update_fields=['status'])
        return Response(ExpenseSerializer(expense).data)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        expenses = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="expenses-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Expense Number', 'Category', 'Amount', 'Date', 'Description', 'Paid By', 'Status'])
        for e in expenses:
            writer.writerow([e.expense_number, e.category, e.amount, e.date, e.description, e.paid_by, e.status])
        return response


def _period_window(period_type, year, month):
    """Returns (start_date, end_date_exclusive, period_label) for the given period type
    ('monthly'|'quarterly'|'yearly'), defaulting the window to the current one if year/month
    aren't given."""
    today = timezone.now().date()
    year = int(year) if year else today.year
    month = int(month) if month else today.month

    if period_type == 'yearly':
        start = today.replace(year=year, month=1, day=1)
        end = start.replace(year=year + 1)
        label = f'{year}'
    elif period_type == 'quarterly':
        quarter = (month - 1) // 3 + 1
        q_start_month = (quarter - 1) * 3 + 1
        start = today.replace(year=year, month=q_start_month, day=1)
        end_month = q_start_month + 3
        if end_month > 12:
            end = start.replace(year=year + 1, month=end_month - 12)
        else:
            end = start.replace(month=end_month)
        label = f'{year}-Q{quarter}'
    else:  # monthly
        start = today.replace(year=year, month=month, day=1)
        end = start.replace(year=year + 1, month=1) if month == 12 else start.replace(month=month + 1)
        label = f'{year}-{month:02d}'

    return start, end, label


class TaxReportView(APIView):
    """Computes GST figures live from real Invoice/PurchaseOrder data for a given period —
    doesn't require a saved TaxReport row. Tax collected mirrors invoicing's "only count paid
    invoices" convention (apps.invoicing.views._reports_summary)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period_type = request.query_params.get('period', 'monthly')
        start, end, label = _period_window(period_type, request.query_params.get('year'), request.query_params.get('month'))

        invoices_qs = filter_queryset_by_role(Invoice.objects.all(), request.user, 'accounting')
        paid_invoices = invoices_qs.filter(status='paid', issue_date__gte=start, issue_date__lt=end)
        total_revenue = paid_invoices.aggregate(t=Sum('total'))['t'] or Decimal('0')
        total_tax_collected = paid_invoices.aggregate(t=Sum('tax'))['t'] or Decimal('0')

        # Purchase orders don't track tax separately from their line-item totals, so we back
        # GST out of the PO total treating it as tax-inclusive (18% GST => tax = total * 18/118).
        # This is a simplification given the data model, not a real tax-paid figure.
        po_total = filter_queryset_by_role(PurchaseOrder.objects.all(), request.user, 'accounting').filter(
            order_date__gte=start, order_date__lt=end,
        ).exclude(status='cancelled').aggregate(t=Sum('total'))['t'] or Decimal('0')
        total_tax_paid = (po_total * Decimal('0.18') / Decimal('1.18')).quantize(Decimal('0.01'))

        net_tax = total_tax_collected - total_tax_paid

        return Response({
            'period': label,
            'total_revenue': str(total_revenue),
            'total_tax_collected': str(total_tax_collected),
            'total_tax_paid': str(total_tax_paid),
            'net_tax': str(net_tax),
        })


class BalanceSheetView(APIView):
    """A simplified single-entity balance sheet derived from real cross-module data. This
    codebase has no populated double-entry ledger to build a textbook balance sheet from, so
    this is pragmatic: receivables/payables from Invoicing & Procurement, cash as a proxy from
    total payments collected, and retained earnings as a plug figure (assets - liabilities)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.invoicing.models import Payment

        invoices_qs = filter_queryset_by_role(Invoice.objects.all(), request.user, 'accounting')
        outstanding_invoices = invoices_qs.filter(status__in=['sent', 'partial', 'overdue'])
        accounts_receivable = (outstanding_invoices.aggregate(t=Sum('total'))['t'] or Decimal('0')) - \
            (outstanding_invoices.aggregate(p=Sum('amount_paid'))['p'] or Decimal('0'))

        # Proxy for cash position — total payments ever recorded. Not a true cash balance
        # (doesn't account for expenses/outflows), just the best signal available in this data model.
        cash_and_bank = filter_queryset_by_role(
            Payment.objects.all(), request.user, 'accounting', user_field='invoice__created_by',
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        total_assets = accounts_receivable + cash_and_bank

        accounts_payable = filter_queryset_by_role(Bill.objects.all(), request.user, 'accounting').filter(
            status='unpaid'
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        total_liabilities = accounts_payable

        retained_earnings = total_assets - total_liabilities
        total_equity = retained_earnings

        return Response({
            'as_of_date': str(timezone.now().date()),
            'assets': {
                'accounts_receivable': str(accounts_receivable),
                'cash_and_bank': str(cash_and_bank),
                'total_assets': str(total_assets),
            },
            'liabilities': {
                'accounts_payable': str(accounts_payable),
                'total_liabilities': str(total_liabilities),
            },
            'equity': {
                'retained_earnings': str(retained_earnings),
                'total_equity': str(total_equity),
            },
        })


class AccountingDashboardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)

        invoices_qs = filter_queryset_by_role(Invoice.objects.all(), request.user, 'accounting')
        expenses_qs = filter_queryset_by_role(Expense.objects.all(), request.user, 'accounting')

        paid_invoices_this_month = invoices_qs.filter(status='paid', issue_date__gte=month_start)
        total_revenue_this_month = paid_invoices_this_month.aggregate(t=Sum('total'))['t'] or Decimal('0')
        tax_collected_this_month = paid_invoices_this_month.aggregate(t=Sum('tax'))['t'] or Decimal('0')

        total_expenses_this_month = expenses_qs.filter(status='approved', date__gte=month_start).aggregate(
            t=Sum('amount')
        )['t'] or Decimal('0')

        net_profit_this_month = total_revenue_this_month - total_expenses_this_month

        overdue_invoices_count = invoices_qs.filter(due_date__lt=today).exclude(status__in=['paid', 'cancelled']).count()

        # Revenue vs expenses for the trailing 6 months (including the current one).
        months = []
        cursor = month_start
        for _ in range(6):
            months.insert(0, cursor)
            cursor = (cursor.replace(day=1) - timedelta(days=1)).replace(day=1)
        revenue_vs_expenses = []
        for m_start in months:
            m_end = m_start.replace(year=m_start.year + 1, month=1) if m_start.month == 12 else m_start.replace(month=m_start.month + 1)
            rev = invoices_qs.filter(status='paid', issue_date__gte=m_start, issue_date__lt=m_end).aggregate(
                t=Sum('total')
            )['t'] or Decimal('0')
            exp = expenses_qs.filter(status='approved', date__gte=m_start, date__lt=m_end).aggregate(
                t=Sum('amount')
            )['t'] or Decimal('0')
            revenue_vs_expenses.append({'month': m_start.strftime('%b %Y'), 'revenue': float(rev), 'expenses': float(exp)})

        # Expense breakdown by category — all-time, since current-month data is likely sparse.
        expense_breakdown_qs = expenses_qs.filter(status='approved').values('category').annotate(
            total=Sum('amount')
        ).order_by('-total')
        expense_breakdown = [{'category': row['category'], 'total': float(row['total'] or 0)} for row in expense_breakdown_qs]

        return Response({
            'total_revenue_this_month': float(total_revenue_this_month),
            'total_expenses_this_month': float(total_expenses_this_month),
            'net_profit_this_month': float(net_profit_this_month),
            'tax_collected_this_month': float(tax_collected_this_month),
            'overdue_invoices_count': overdue_invoices_count,
            'revenue_vs_expenses': revenue_vs_expenses,
            'expense_breakdown': expense_breakdown,
        })
