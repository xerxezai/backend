import calendar
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated

from apps.crm.models import Customer, Lead, Deal
from apps.sales.models import SalesOrder, Quotation
from apps.invoicing.models import Invoice, Payment
from apps.inventory.models import Product, StockMovement
from apps.hr.models import Employee, LeaveRequest
from apps.purchases.models import PurchaseOrder
from apps.mlm.models import Commission
from apps.rbac.utils import get_user_role


def _dashboard_scope(user):
    """Role-scoped base querysets for dashboard/report aggregates.

    Super Admins see company-wide numbers. Everyone else (module admin,
    regular user, read only) sees only data they own — either directly via
    created_by, or through the customer/employee they created for models
    that don't carry created_by themselves. Models with no ownership path
    at all (legacy purchases, MLM commissions) scope to empty for them.
    """
    if user.is_superuser or get_user_role(user) == 'super_admin':
        return {
            'customers': Customer.objects.all(),
            'leads': Lead.objects.all(),
            'deals': Deal.objects.all(),
            'orders': SalesOrder.objects.all(),
            'quotations': Quotation.objects.all(),
            'invoices': Invoice.objects.all(),
            'movements': StockMovement.objects.all(),
            'employees': Employee.objects.all(),
            'leaves': LeaveRequest.objects.all(),
            'purchase_orders': PurchaseOrder.objects.all(),
            'commissions': Commission.objects.all(),
        }
    return {
        'customers': Customer.objects.filter(created_by=user),
        'leads': Lead.objects.filter(created_by=user),
        'deals': Deal.objects.filter(customer__created_by=user),
        'orders': SalesOrder.objects.filter(created_by=user),
        'quotations': Quotation.objects.filter(customer__created_by=user),
        'invoices': Invoice.objects.filter(customer__created_by=user),
        'movements': StockMovement.objects.filter(created_by=user),
        'employees': Employee.objects.filter(created_by=user),
        'leaves': LeaveRequest.objects.filter(employee__created_by=user),
        'purchase_orders': PurchaseOrder.objects.none(),
        'commissions': Commission.objects.none(),
    }


class ERPDashboardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)
        scope = _dashboard_scope(request.user)

        # Total Revenue = paid invoices + won CRM deals (a deal can close without ever
        # being invoiced separately, e.g. services billed outside the invoicing flow).
        paid_invoices_total = scope['invoices'].filter(status='paid').aggregate(t=Sum('total'))['t'] or Decimal('0')
        won_deals_total = scope['deals'].filter(stage='won').aggregate(t=Sum('value'))['t'] or Decimal('0')
        total_revenue = paid_invoices_total + won_deals_total

        # This Month = paid invoices issued this month + won deals closed this month.
        # Deal has no dedicated "closed_at" field, so updated_at (bumped whenever the
        # deal is saved, including the stage/ action's PATCH to 'won') is used as the
        # closed-date proxy.
        month_paid_invoices = scope['invoices'].filter(status='paid', issue_date__gte=month_start).aggregate(t=Sum('total'))['t'] or Decimal('0')
        month_won_deals = scope['deals'].filter(stage='won', updated_at__date__gte=month_start).aggregate(t=Sum('value'))['t'] or Decimal('0')
        month_revenue = month_paid_invoices + month_won_deals

        # Outstanding = unpaid invoices + accepted quotations that haven't been invoiced
        # yet (no linked sales order, or a sales order with no invoice against it).
        unpaid_invoices_total = scope['invoices'].filter(status__in=['sent', 'partial', 'overdue']).aggregate(t=Sum('total'))['t'] or Decimal('0')
        invoiced_order_ids = set(
            scope['invoices'].exclude(sales_order__isnull=True).values_list('sales_order_id', flat=True)
        )
        uninvoiced_quotations_total = Decimal('0')
        for q in scope['quotations'].filter(status='accepted').prefetch_related('orders'):
            order = q.orders.first()
            if not order or order.id not in invoiced_order_ids:
                uninvoiced_quotations_total += q.total
        outstanding = unpaid_invoices_total + uninvoiced_quotations_total

        # Last 6 months, computed in Python (DB-agnostic) rather than DATE_TRUNC —
        # each bucket = [1st of month, 1st of next month).
        monthly_trend = []
        anchor = month_start
        for i in range(5, -1, -1):
            year = anchor.year
            month = anchor.month - i
            while month <= 0:
                month += 12
                year -= 1
            bucket_start = anchor.replace(year=year, month=month, day=1)
            days_in_month = calendar.monthrange(year, month)[1]
            bucket_end = bucket_start + timedelta(days=days_in_month)

            revenue = scope['invoices'].filter(
                status='paid', issue_date__gte=bucket_start, issue_date__lt=bucket_end,
            ).aggregate(t=Sum('total'))['t'] or Decimal('0')
            new_customers = scope['customers'].filter(
                created_at__date__gte=bucket_start, created_at__date__lt=bucket_end,
            ).count()

            monthly_trend.append({
                'month': bucket_start.strftime('%b'),
                'revenue': float(revenue),
                'customers': new_customers,
            })

        return Response({
            'monthly_trend': monthly_trend,
            'crm': {
                'total_customers': scope['customers'].filter(is_active=True).count(),
                'total_leads': scope['leads'].count(),
                'new_leads_this_month': scope['leads'].filter(created_at__date__gte=month_start).count(),
                'leads_by_status': list(scope['leads'].values('status').annotate(count=Count('id'))),
            },
            'sales': {
                'total_orders': scope['orders'].count(),
                'open_orders': scope['orders'].filter(status='open').count(),
                'total_quotations': scope['quotations'].count(),
                'pending_quotations': scope['quotations'].filter(status='sent').count(),
            },
            'finance': {
                'total_revenue': str(total_revenue),
                'month_revenue': str(month_revenue),
                'outstanding_invoices': str(outstanding),
                'total_invoices': scope['invoices'].count(),
                'overdue_invoices': scope['invoices'].filter(status='overdue').count(),
            },
            'inventory': {
                'total_products': Product.objects.filter(is_active=True).count(),
                'stock_movements_this_month': scope['movements'].filter(occurred_at__date__gte=month_start).count(),
            },
            'hr': {
                'total_employees': scope['employees'].filter(status='active').count(),
                'pending_leave_requests': scope['leaves'].filter(status='pending').count(),
            },
            'purchases': {
                'total_purchase_orders': scope['purchase_orders'].count(),
                'pending_orders': scope['purchase_orders'].filter(status__in=['draft', 'sent']).count(),
            },
            'mlm': {
                'total_commissions': str(scope['commissions'].aggregate(t=Sum('amount'))['t'] or Decimal('0')),
                'pending_commissions': str(scope['commissions'].filter(status='pending').aggregate(t=Sum('amount'))['t'] or Decimal('0')),
            },
        })


class RecentActivityView(APIView):
    """Unified recent-activity feed built from real, already-timestamped
    ERP records (no separate audit-log model needed)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = []
        scope = _dashboard_scope(request.user)

        for lead in scope['leads'].order_by('-created_at')[:5]:
            items.append({
                'id': f'lead-{lead.id}',
                'type': 'crm',
                'title': f'New lead: {lead.name}',
                'subtitle': lead.company or (lead.get_source_display() if hasattr(lead, 'get_source_display') else lead.source),
                'timestamp': lead.created_at,
            })

        for inv in scope['invoices'].select_related('customer').order_by('-created_at')[:5]:
            items.append({
                'id': f'invoice-{inv.id}',
                'type': 'finance',
                'title': f'Invoice {inv.number} — {inv.get_status_display()}',
                'subtitle': inv.customer.name if inv.customer_id else '',
                'timestamp': inv.created_at,
            })

        for lr in scope['leaves'].select_related('employee').order_by('-created_at')[:5]:
            items.append({
                'id': f'leave-{lr.id}',
                'type': 'hr',
                'title': f'{lr.employee.full_name} requested {lr.get_type_display().lower()} leave',
                'subtitle': lr.get_status_display(),
                'timestamp': lr.created_at,
            })

        for po in scope['purchase_orders'].select_related('vendor').order_by('-created_at')[:5]:
            items.append({
                'id': f'po-{po.id}',
                'type': 'sales',
                'title': f'Purchase order {po.number} — {po.get_status_display()}',
                'subtitle': po.vendor.name if po.vendor_id else '',
                'timestamp': po.created_at,
            })

        items.sort(key=lambda x: x['timestamp'], reverse=True)
        items = items[:10]

        now = timezone.now()

        def time_ago(ts):
            delta = now - ts
            seconds = delta.total_seconds()
            if seconds < 60:
                return 'just now'
            if seconds < 3600:
                return f'{int(seconds // 60)} min ago'
            if seconds < 86400:
                return f'{int(seconds // 3600)}h ago'
            days = int(seconds // 86400)
            return f'{days}d ago'

        data = [{
            'id': it['id'],
            'type': it['type'],
            'title': it['title'],
            'subtitle': it['subtitle'],
            'time_ago': time_ago(it['timestamp']),
            'timestamp': it['timestamp'].isoformat(),
        } for it in items]

        return Response(data)


class SalesReportView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = SalesOrder.objects.values('status').annotate(count=Count('id'), total=Sum('total'))
        invoices = Invoice.objects.values('status').annotate(count=Count('id'), total=Sum('total'))
        monthly = (
            Invoice.objects.filter(status='paid')
            .extra(select={'month': "DATE_TRUNC('month', issue_date)"})
            .values('month')
            .annotate(total=Sum('total'))
            .order_by('month')
        )
        return Response({
            'orders_by_status': list(orders),
            'invoices_by_status': list(invoices),
            'monthly_revenue': list(monthly),
        })


class HRReportView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employees_by_dept = Employee.objects.values('department__name').annotate(count=Count('id'))
        employees_by_status = Employee.objects.values('status').annotate(count=Count('id'))
        leave_by_type = LeaveRequest.objects.values('type').annotate(count=Count('id'))
        return Response({
            'employees_by_department': list(employees_by_dept),
            'employees_by_status': list(employees_by_status),
            'leave_by_type': list(leave_by_type),
        })


class InventoryReportView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        products_by_category = Product.objects.values('category__name').annotate(count=Count('id'))
        movements_by_type = StockMovement.objects.values('type').annotate(count=Count('id'), qty=Sum('quantity'))
        return Response({
            'products_by_category': list(products_by_category),
            'stock_movements_by_type': list(movements_by_type),
        })
