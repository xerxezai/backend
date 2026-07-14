import csv
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Sum, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.inventory.models import Product, Warehouse, StockMovement
from .models import Supplier, PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem, Bill, next_number
from .serializers import (
    SupplierSerializer, PurchaseOrderSerializer, PurchaseOrderItemSerializer,
    GoodsReceiptSerializer, BillSerializer,
)


def _create_goods_receipt(*, purchase_order, received_date, notes, items_data, user):
    """Shared by GoodsReceiptViewSet.create and PurchaseOrder.receive — creates the receipt
    + its line items, books an inbound StockMovement per item (so inventory stays the single
    source of truth for stock, same as every other module) and marks the PO received."""
    receipt = GoodsReceipt.objects.create(
        receipt_number=next_number(GoodsReceipt, 'receipt_number', 'GR'),
        purchase_order=purchase_order,
        received_date=received_date or timezone.now().date(),
        received_by=user if user and getattr(user, 'is_authenticated', False) else None,
        notes=notes or '',
    )
    warehouse = Warehouse.objects.filter(is_active=True).first() or Warehouse.objects.first()
    now = timezone.now()
    product_ids = [i.get('product') for i in items_data if i.get('product')]
    products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

    for item in items_data:
        product = products.get(item.get('product'))
        try:
            qty = Decimal(str(item.get('quantity_received') or 0))
        except InvalidOperation:
            qty = Decimal('0')
        GoodsReceiptItem.objects.create(goods_receipt=receipt, product=product, quantity_received=qty)
        if product and warehouse and qty > 0:
            StockMovement.objects.create(
                type='in', product=product, warehouse=warehouse, quantity=qty,
                reference=receipt.receipt_number, reason='Goods receipt',
                occurred_at=now, notes=f'Received against PO {purchase_order.po_number}',
                created_by=user if user and getattr(user, 'is_authenticated', False) else None,
            )

    purchase_order.status = 'received'
    purchase_order.save(update_fields=['status'])
    return receipt


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'email', 'city', 'country']
    filterset_fields = ['is_active']

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        suppliers = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="suppliers-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Phone', 'City', 'Country', 'Payment Terms', 'Rating', 'Active'])
        for s in suppliers:
            writer.writerow([s.name, s.email, s.phone, s.city, s.country, s.payment_terms, s.rating, s.is_active])
        return response


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.select_related('supplier').prefetch_related('items__product').all()
    serializer_class = PurchaseOrderSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['po_number', 'supplier__name']
    filterset_fields = {
        'status': ['exact'],
        'supplier': ['exact'],
        'order_date': ['exact', 'gte', 'lte'],
    }
    ordering_fields = ['order_date', 'total']

    @action(detail=True, methods=['put', 'post'], url_path='send')
    def send(self, request, pk=None):
        po = self.get_object()
        if po.status in ('received', 'cancelled'):
            return Response(
                {'detail': f'Cannot send a purchase order that is already {po.get_status_display().lower()}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        po.status = 'sent'
        po.save(update_fields=['status'])
        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=['post'], url_path='receive')
    def receive(self, request, pk=None):
        po = self.get_object()
        if po.status == 'cancelled':
            return Response({'detail': 'Cannot receive goods for a cancelled purchase order.'}, status=status.HTTP_400_BAD_REQUEST)
        if po.status == 'received':
            return Response({'detail': 'This purchase order has already been received.'}, status=status.HTTP_400_BAD_REQUEST)
        items_data = request.data.get('items') or [
            {'product': i.product_id, 'quantity_received': i.quantity} for i in po.items.all()
        ]
        receipt = _create_goods_receipt(
            purchase_order=po,
            received_date=request.data.get('received_date'),
            notes=request.data.get('notes', ''),
            items_data=items_data,
            user=request.user,
        )
        return Response(GoodsReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        pos = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="purchase-orders-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['PO Number', 'Supplier', 'Order Date', 'Expected Delivery', 'Status', 'Total'])
        for po in pos:
            writer.writerow([po.po_number, po.supplier.name, po.order_date, po.expected_delivery, po.status, po.total])
        return response


class PurchaseOrderItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrderItem.objects.select_related('purchase_order', 'product').all()
    serializer_class = PurchaseOrderItemSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['purchase_order']


class GoodsReceiptViewSet(viewsets.ModelViewSet):
    queryset = GoodsReceipt.objects.select_related('purchase_order', 'purchase_order__supplier', 'received_by').prefetch_related('items__product').all()
    serializer_class = GoodsReceiptSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['purchase_order']

    def create(self, request, *args, **kwargs):
        po_id = request.data.get('purchase_order')
        try:
            po = PurchaseOrder.objects.get(pk=po_id)
        except (PurchaseOrder.DoesNotExist, TypeError, ValueError):
            return Response({'detail': 'A valid purchase_order is required.'}, status=status.HTTP_400_BAD_REQUEST)
        items_data = request.data.get('items') or []
        receipt = _create_goods_receipt(
            purchase_order=po,
            received_date=request.data.get('received_date'),
            notes=request.data.get('notes', ''),
            items_data=items_data,
            user=request.user,
        )
        return Response(GoodsReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        # Reverses the inbound StockMovements this receipt created (matched by reference=
        # receipt_number, the same value they were tagged with in _create_goods_receipt) so
        # deleting a receipt can't leave inventory overstated. The PO's status is left as
        # 'received' — reopening it isn't safe to infer automatically.
        StockMovement.objects.filter(reference=instance.receipt_number, type='in', reason='Goods receipt').delete()
        instance.delete()


class BillViewSet(viewsets.ModelViewSet):
    queryset = Bill.objects.select_related('supplier', 'purchase_order').all()
    serializer_class = BillSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['bill_number', 'supplier__name', 'purchase_order__po_number']
    filterset_fields = {
        'status': ['exact'],
        'supplier': ['exact'],
        'issue_date': ['exact', 'gte', 'lte'],
        'due_date': ['exact', 'gte', 'lte'],
    }
    ordering_fields = ['issue_date', 'due_date', 'amount']

    @action(detail=True, methods=['put', 'post'], url_path='mark-paid')
    def mark_paid(self, request, pk=None):
        bill = self.get_object()
        bill.status = 'paid'
        bill.save(update_fields=['status'])
        return Response(BillSerializer(bill).data)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        bills = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="bills-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Bill Number', 'Supplier', 'PO Number', 'Issue Date', 'Due Date', 'Amount', 'Status'])
        for b in bills:
            writer.writerow([b.bill_number, b.supplier.name, b.purchase_order.po_number if b.purchase_order_id else '', b.issue_date, b.due_date, b.amount, b.status])
        return response


class ProcurementDashboardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)

        total_orders = PurchaseOrder.objects.count()
        pending_orders = PurchaseOrder.objects.filter(status__in=['draft', 'sent']).count()
        total_spent_this_month = PurchaseOrder.objects.filter(order_date__gte=month_start).exclude(
            status='cancelled'
        ).aggregate(t=Sum('total'))['t'] or Decimal('0')
        overdue_bills = Bill.objects.filter(status='unpaid', due_date__lt=today).count()

        recent_orders = PurchaseOrder.objects.select_related('supplier').order_by('-order_date', '-id')[:8]

        top_suppliers_qs = Supplier.objects.annotate(
            spend=Sum('purchase_orders__total', filter=~Q(purchase_orders__status='cancelled'))
        ).filter(spend__isnull=False).order_by('-spend')[:5]
        top_suppliers = [{'id': s.id, 'name': s.name, 'spend': float(s.spend or 0)} for s in top_suppliers_qs]

        # Monthly spending for the trailing 6 months (including the current one).
        months = []
        cursor = month_start
        for _ in range(6):
            months.insert(0, cursor)
            cursor = (cursor - timedelta(days=1)).replace(day=1)
        monthly_spending = []
        for m_start in months:
            m_end = m_start.replace(year=m_start.year + 1, month=1) if m_start.month == 12 else m_start.replace(month=m_start.month + 1)
            total = PurchaseOrder.objects.filter(order_date__gte=m_start, order_date__lt=m_end).exclude(
                status='cancelled'
            ).aggregate(t=Sum('total'))['t'] or Decimal('0')
            monthly_spending.append({'month': m_start.strftime('%b %Y'), 'total': float(total)})

        return Response({
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'total_spent_this_month': float(total_spent_this_month),
            'overdue_bills': overdue_bills,
            'recent_orders': PurchaseOrderSerializer(recent_orders, many=True).data,
            'top_suppliers': top_suppliers,
            'monthly_spending': monthly_spending,
        })
