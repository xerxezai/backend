from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from apps.crm.models import Customer, Lead
from apps.sales.models import SalesOrder, Quotation
from apps.invoicing.models import Invoice, Payment
from apps.inventory.models import Product, StockMovement
from apps.hr.models import Employee, LeaveRequest
from apps.purchases.models import PurchaseOrder
from apps.mlm.models import Commission, Earning


class ERPDashboardView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)

        total_revenue = Invoice.objects.filter(status='paid').aggregate(t=Sum('total'))['t'] or Decimal('0')
        month_revenue = Invoice.objects.filter(status='paid', issue_date__gte=month_start).aggregate(t=Sum('total'))['t'] or Decimal('0')
        outstanding = Invoice.objects.filter(status__in=['sent', 'partial', 'overdue']).aggregate(t=Sum('total'))['t'] or Decimal('0')

        return Response({
            'crm': {
                'total_customers': Customer.objects.filter(is_active=True).count(),
                'total_leads': Lead.objects.count(),
                'new_leads_this_month': Lead.objects.filter(created_at__date__gte=month_start).count(),
                'leads_by_status': list(Lead.objects.values('status').annotate(count=Count('id'))),
            },
            'sales': {
                'total_orders': SalesOrder.objects.count(),
                'open_orders': SalesOrder.objects.filter(status='open').count(),
                'total_quotations': Quotation.objects.count(),
                'pending_quotations': Quotation.objects.filter(status='sent').count(),
            },
            'finance': {
                'total_revenue': str(total_revenue),
                'month_revenue': str(month_revenue),
                'outstanding_invoices': str(outstanding),
                'total_invoices': Invoice.objects.count(),
                'overdue_invoices': Invoice.objects.filter(status='overdue').count(),
            },
            'inventory': {
                'total_products': Product.objects.filter(is_active=True).count(),
                'stock_movements_this_month': StockMovement.objects.filter(occurred_at__date__gte=month_start).count(),
            },
            'hr': {
                'total_employees': Employee.objects.filter(status='active').count(),
                'pending_leave_requests': LeaveRequest.objects.filter(status='pending').count(),
            },
            'purchases': {
                'total_purchase_orders': PurchaseOrder.objects.count(),
                'pending_orders': PurchaseOrder.objects.filter(status__in=['draft', 'sent']).count(),
            },
            'mlm': {
                'total_commissions': str(Commission.objects.aggregate(t=Sum('amount'))['t'] or Decimal('0')),
                'pending_commissions': str(Commission.objects.filter(status='pending').aggregate(t=Sum('amount'))['t'] or Decimal('0')),
            },
        })


class SalesReportView(APIView):
    authentication_classes = [TokenAuthentication]
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
    authentication_classes = [TokenAuthentication]
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
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        products_by_category = Product.objects.values('category__name').annotate(count=Count('id'))
        movements_by_type = StockMovement.objects.values('type').annotate(count=Count('id'), qty=Sum('quantity'))
        return Response({
            'products_by_category': list(products_by_category),
            'stock_movements_by_type': list(movements_by_type),
        })
