from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Quotation, QuotationItem, SalesOrder, SalesOrderItem
from .serializers import QuotationSerializer, QuotationItemSerializer, SalesOrderSerializer
from apps.mlm.models import Distributor, generate_commission_for_order
from apps.inventory.models import StockMovement, Warehouse


def generate_stock_out_for_order(order, user=None):
    """Books one 'out' StockMovement per line item the first time a SalesOrder reaches
    'confirmed' or 'fulfilled' — idempotent via reference=order.number (mirrors
    _create_goods_receipt's use of receipt_number), so re-saving an already-confirmed
    order never double-books. Skips line items with no product (free-text-only rows)."""
    if order.status not in ('confirmed', 'fulfilled'):
        return
    if StockMovement.objects.filter(reference=order.number, type='out').exists():
        return
    warehouse = Warehouse.objects.filter(is_active=True).first() or Warehouse.objects.first()
    if not warehouse:
        return
    now = timezone.now()
    for item in order.items.select_related('product').all():
        if not item.product_id or not item.quantity or item.quantity <= 0:
            continue
        StockMovement.objects.create(
            type='out', product=item.product, warehouse=warehouse, quantity=item.quantity,
            reference=order.number, reason=f'Sales Order {order.number}', occurred_at=now,
            notes='Auto-booked when the order was confirmed.',
            created_by=user if user and getattr(user, 'is_authenticated', False) else None,
        )


class QuotationViewSet(viewsets.ModelViewSet):
    queryset = Quotation.objects.select_related('customer').prefetch_related('items').all()
    serializer_class = QuotationSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['number', 'customer__name']
    filterset_fields = {
        'status': ['exact'],
        'customer': ['exact'],
        'issue_date': ['exact', 'gte', 'lte'],
    }
    ordering_fields = ['issue_date', 'total']

    @action(detail=True, methods=['post'], url_path='convert')
    def convert(self, request, pk=None):
        """Convert this quotation into a sales order. One quotation converts at most once."""
        quotation = self.get_object()
        if quotation.orders.exists():
            existing = quotation.orders.first()
            return Response(
                {'detail': f'Already converted to order {existing.number}.', 'order': SalesOrderSerializer(existing).data},
                status=status.HTTP_400_BAD_REQUEST,
            )
        last = SalesOrder.objects.order_by('-id').first()
        next_n = 1
        if last and last.number.startswith('SO-') and last.number[3:].isdigit():
            next_n = int(last.number[3:]) + 1
        order = SalesOrder.objects.create(
            number=f'SO-{next_n:03d}',
            customer=quotation.customer,
            quotation=quotation,
            salesperson=request.user,
            order_date=timezone.now().date(),
            status='open',
            subtotal=quotation.subtotal,
            tax=quotation.tax,
            total=quotation.total,
            notes=quotation.notes,
        )
        # Carry the quotation's line items over so the order (and any invoice later
        # generated from it) has real items to total from, instead of falling back to
        # a single synthetic line that re-applies GST on top of an already-taxed amount.
        SalesOrderItem.objects.bulk_create([
            SalesOrderItem(
                order=order, product_id=item.product_id, description=item.description,
                quantity=item.quantity, unit_price=item.unit_price, line_total=item.line_total,
            )
            for item in quotation.items.all()
        ])
        quotation.status = 'accepted'
        quotation.save(update_fields=['status'])
        return Response(SalesOrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='expiring')
    def expiring(self, request):
        """Quotations whose valid_until falls within the next 3 days (inclusive), not already closed out."""
        today = timezone.now().date()
        soon = today + timedelta(days=3)
        qs = self.get_queryset().filter(
            valid_until__isnull=False, valid_until__gte=today, valid_until__lte=soon,
        ).exclude(status__in=['accepted', 'rejected', 'expired'])
        return Response(QuotationSerializer(qs, many=True).data)


class QuotationItemViewSet(viewsets.ModelViewSet):
    queryset = QuotationItem.objects.select_related('quotation', 'product').all()
    serializer_class = QuotationItemSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['quotation']


class SalesOrderViewSet(viewsets.ModelViewSet):
    queryset = SalesOrder.objects.select_related('customer', 'quotation', 'salesperson', 'distributor').all()
    serializer_class = SalesOrderSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['number', 'customer__name']
    filterset_fields = ['status', 'customer', 'salesperson', 'distributor']
    ordering_fields = ['order_date', 'total']

    def _maybe_generate_commission(self, order):
        """Fires after every create/update/status-change — safe and idempotent regardless of
        which specific field changed, see generate_commission_for_order's docstring."""
        if order.status == 'confirmed' and order.distributor_id:
            generate_commission_for_order(order)

    def _maybe_book_stock_out(self, order, user=None):
        generate_stock_out_for_order(order, user=user)

    def perform_create(self, serializer):
        order = serializer.save()
        self._maybe_generate_commission(order)
        self._maybe_book_stock_out(order, user=self.request.user)

    def perform_update(self, serializer):
        order = serializer.save()
        self._maybe_generate_commission(order)
        self._maybe_book_stock_out(order, user=self.request.user)

    @action(detail=True, methods=['put', 'patch'], url_path='status')
    def update_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')
        valid = dict(SalesOrder.STATUS)
        if new_status not in valid:
            return Response(
                {'detail': f'Invalid status. Choose one of: {", ".join(valid)}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.status = new_status
        order.save(update_fields=['status'])
        self._maybe_generate_commission(order)
        self._maybe_book_stock_out(order, user=request.user)
        return Response(SalesOrderSerializer(order).data)

    @action(detail=False, methods=['get'], url_path='salespeople')
    def salespeople(self, request):
        """Combined list for the 'Assign Salesperson' dropdown: regular Users and active MLM
        Distributors, tagged by `type` so the frontend can set the right FK (salesperson vs
        distributor) on the order. Any authenticated user may read it."""
        User = get_user_model()
        users = User.objects.filter(is_active=True).order_by('username').values('id', 'username', 'first_name', 'last_name')
        people = [
            {'type': 'user', 'id': u['id'], 'name': (f"{u['first_name']} {u['last_name']}".strip() or u['username'])}
            for u in users
        ]
        distributors = Distributor.objects.filter(status='active').order_by('name')
        people += [
            {'type': 'distributor', 'id': d.id, 'name': f'{d.name} ({d.distributor_id})'}
            for d in distributors
        ]
        return Response(people)


class SalesDashboardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)

        total_sales_this_month = SalesOrder.objects.filter(
            order_date__gte=month_start, order_date__lte=today,
        ).aggregate(s=Sum('total'))['s'] or 0
        total_quotations_this_month = Quotation.objects.filter(
            issue_date__gte=month_start, issue_date__lte=today,
        ).count()

        top_5_customers = list(
            SalesOrder.objects.values('customer_id', 'customer__name')
            .annotate(revenue=Sum('total'))
            .order_by('-revenue')[:5]
        )
        top_5_customers = [
            {'customer_id': r['customer_id'], 'customer_name': r['customer__name'], 'revenue': float(r['revenue'] or 0)}
            for r in top_5_customers
        ]

        # revenue_last_6_months — oldest to newest, computed without external date libs
        month_starts = []
        y, m = month_start.year, month_start.month
        for _ in range(6):
            month_starts.append(month_start.__class__(y, m, 1))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        month_starts.reverse()

        revenue_last_6_months = []
        for i, ms in enumerate(month_starts):
            if i + 1 < len(month_starts):
                me = month_starts[i + 1]
            else:
                ny, nm = (ms.year + 1, 1) if ms.month == 12 else (ms.year, ms.month + 1)
                me = ms.replace(year=ny, month=nm)
            total = SalesOrder.objects.filter(order_date__gte=ms, order_date__lt=me).aggregate(s=Sum('total'))['s'] or 0
            revenue_last_6_months.append({'month': ms.strftime('%b %Y'), 'revenue': float(total)})

        sales_by_product = list(
            QuotationItem.objects.filter(product__isnull=False)
            .values('product_id', 'product__name')
            .annotate(revenue=Sum('line_total'))
            .order_by('-revenue')[:10]
        )
        sales_by_product = [
            {'product_id': r['product_id'], 'product_name': r['product__name'], 'revenue': float(r['revenue'] or 0)}
            for r in sales_by_product
        ]

        return Response({
            'total_sales_this_month': float(total_sales_this_month),
            'total_quotations_this_month': total_quotations_this_month,
            'top_5_customers': top_5_customers,
            'revenue_last_6_months': revenue_last_6_months,
            'sales_by_product': sales_by_product,
        })
