import csv
import io
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum, Case, When, F, Value, DecimalField
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.mixins import ProtectedDestroyMixin
from .models import ProductCategory, Product, Warehouse, StockMovement
from .serializers import ProductCategorySerializer, ProductSerializer, WarehouseSerializer, StockMovementSerializer, _gen_code


def stock_delta_case():
    """SQL Case expression computing a movement's signed effect on stock, per StockMovement's sign convention."""
    return Case(
        When(stock_movements__type__in=StockMovement.POSITIVE_TYPES, then=F('stock_movements__quantity')),
        When(stock_movements__type__in=StockMovement.NEGATIVE_TYPES, then=-F('stock_movements__quantity')),
        default=Value(0),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


def products_with_stock():
    """Product queryset annotated with current_stock — the one place this aggregation is built."""
    return Product.objects.select_related('category').annotate(
        current_stock=Coalesce(Sum(stock_delta_case()), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
    ).order_by('name')


class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code']


class ProductViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'code', 'description', 'barcode']
    filterset_fields = ['category', 'is_active', 'is_digital', 'unit']

    def get_queryset(self):
        qs = products_with_stock()
        # `status` is an alias for is_active (matches the frontend's Products status filter)
        status_param = self.request.query_params.get('status')
        if status_param in ('true', 'false'):
            qs = qs.filter(is_active=(status_param == 'true'))
        if str(self.request.query_params.get('low_stock', '')).lower() in ('1', 'true', 'yes'):
            qs = qs.filter(current_stock__lt=F('min_stock_level'))
        return qs

    @action(detail=False, methods=['get'], url_path='low-stock')
    def low_stock(self, request):
        qs = self.get_queryset().filter(current_stock__lt=F('min_stock_level'))
        return Response(ProductSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='dead-stock')
    def dead_stock(self, request):
        """Active products with no stock movement in the last 90 days (including products with none at all)."""
        cutoff = timezone.now() - timedelta(days=90)
        qs = self.get_queryset().filter(is_active=True).exclude(stock_movements__occurred_at__gte=cutoff)
        return Response(ProductSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='bulk-import', parser_classes=[MultiPartParser, FormParser])
    def bulk_import(self, request):
        """Accepts a CSV file (field name 'file') with columns: name, code, category, unit,
        cost_price, sale_price, min_stock_level, barcode. Only 'name' is required per row."""
        f = request.FILES.get('file')
        if not f:
            return Response({'detail': 'No file uploaded. Send it as multipart field "file".'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            text = f.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response({'detail': 'File must be UTF-8 encoded CSV.'}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(io.StringIO(text))
        to_create, row_numbers, errors = [], [], []
        categories_by_name = {c.name.lower(): c for c in ProductCategory.objects.all()}
        valid_units = {u for u, _ in Product.UNIT}

        # _gen_code() re-queries count()+exists() per call, which is both a per-row
        # DB round trip and, if called repeatedly before any row is actually saved
        # (as a single bulk_create requires), would hand out the same duplicate code
        # to every row. Generate auto-assigned codes for this import up front, tracked
        # in memory alongside any explicit codes rows supply in the CSV.
        next_n = Product.objects.count()
        existing_codes = set(Product.objects.values_list('code', flat=True))

        def next_code():
            nonlocal next_n
            while True:
                next_n += 1
                code = f"PROD{str(next_n).zfill(4)}"
                if code not in existing_codes:
                    existing_codes.add(code)
                    return code

        for i, row in enumerate(reader, start=2):  # row 1 is the header
            row = {(k or '').strip(): (v or '').strip() for k, v in row.items()}
            name = row.get('name')
            if not name:
                errors.append({'row': i, 'error': 'Missing "name".'})
                continue
            try:
                category = None
                cat_name = row.get('category')
                if cat_name:
                    category = categories_by_name.get(cat_name.lower())
                    if category is None:
                        errors.append({'row': i, 'error': f'Unknown category "{cat_name}".'})
                        continue
                unit = row.get('unit') or 'pcs'
                if unit not in valid_units:
                    errors.append({'row': i, 'error': f'Invalid unit "{unit}".'})
                    continue
                code = row.get('code') or ''
                if code:
                    existing_codes.add(code)
                else:
                    code = next_code()
                product = Product(
                    name=name,
                    code=code,
                    category=category,
                    unit=unit,
                    cost_price=Decimal(row.get('cost_price') or '0'),
                    sale_price=Decimal(row.get('sale_price') or '0'),
                    min_stock_level=Decimal(row.get('min_stock_level') or '0'),
                    barcode=row.get('barcode') or '',
                )
                product.full_clean(exclude=['image'])
                to_create.append(product)
                row_numbers.append(i)
            except (InvalidOperation, ValueError) as exc:
                errors.append({'row': i, 'error': f'Invalid number: {exc}'})
            except Exception as exc:
                errors.append({'row': i, 'error': str(exc)})

        with transaction.atomic():
            Product.objects.bulk_create(to_create, batch_size=500)

        created = [
            {'row': row_i, 'id': p.id, 'name': p.name, 'code': p.code}
            for row_i, p in zip(row_numbers, to_create)
        ]
        return Response({'created_count': len(created), 'created': created, 'errors': errors}, status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST)


class WarehouseViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    queryset = Warehouse.objects.prefetch_related('stock_movements__product').all()
    serializer_class = WarehouseSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code']


class StockTransferView(APIView):
    """Moves stock between two warehouses as a paired 'out' + 'in' movement (atomic)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get('product')
        from_id = request.data.get('from_warehouse')
        to_id = request.data.get('to_warehouse')
        quantity = request.data.get('quantity')
        notes = request.data.get('notes', '')

        if not all([product_id, from_id, to_id, quantity]):
            return Response({'detail': 'product, from_warehouse, to_warehouse and quantity are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if str(from_id) == str(to_id):
            return Response({'detail': 'Source and destination warehouse must differ.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            quantity = Decimal(str(quantity))
            if quantity <= 0:
                raise InvalidOperation
        except InvalidOperation:
            return Response({'detail': 'Quantity must be a positive number.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(pk=product_id)
            from_wh = Warehouse.objects.get(pk=from_id)
            to_wh = Warehouse.objects.get(pk=to_id)
        except (Product.DoesNotExist, Warehouse.DoesNotExist):
            return Response({'detail': 'Product or warehouse not found.'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        reference = f'TRANSFER-{now.strftime("%Y%m%d%H%M%S")}'
        with transaction.atomic():
            out_move = StockMovement.objects.create(
                type='out', product=product, warehouse=from_wh, quantity=quantity,
                reference=reference, reason='Stock transfer', occurred_at=now,
                notes=f'Transferred to {to_wh.name}. {notes}'.strip(),
                created_by=request.user if request.user.is_authenticated else None,
            )
            in_move = StockMovement.objects.create(
                type='in', product=product, warehouse=to_wh, quantity=quantity,
                reference=reference, reason='Stock transfer', occurred_at=now,
                notes=f'Transferred from {from_wh.name}. {notes}'.strip(),
                created_by=request.user if request.user.is_authenticated else None,
            )
        return Response({
            'reference': reference,
            'out': StockMovementSerializer(out_move).data,
            'in': StockMovementSerializer(in_move).data,
        }, status=status.HTTP_201_CREATED)


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.select_related('product', 'warehouse', 'created_by').all()
    serializer_class = StockMovementSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = {
        'type': ['exact'],
        'product': ['exact'],
        'warehouse': ['exact'],
        'occurred_at': ['gte', 'lte'],
    }
    ordering_fields = ['occurred_at']

    def get_queryset(self):
        # Inventory sits under the Procurement module in this ERP's RBAC scheme.
        from apps.rbac.utils import filter_queryset_by_role
        return filter_queryset_by_role(super().get_queryset(), self.request.user, 'procurement')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)


class InventoryDashboardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        products = list(products_with_stock().filter(is_active=True))

        total_value = sum((Decimal(p.current_stock or 0) * (p.cost_price or Decimal('0')) for p in products), Decimal('0'))

        low_stock = [p for p in products if Decimal(p.current_stock or 0) < (p.min_stock_level or Decimal('0'))]
        low_stock_items = [
            {'id': p.id, 'name': p.name, 'code': p.code, 'current_stock': float(p.current_stock or 0), 'min_stock_level': float(p.min_stock_level or 0)}
            for p in low_stock
        ]

        by_value = sorted(products, key=lambda p: Decimal(p.current_stock or 0) * (p.cost_price or Decimal('0')), reverse=True)
        top_5_products_by_value = [
            {'id': p.id, 'name': p.name, 'code': p.code, 'value': float(Decimal(p.current_stock or 0) * (p.cost_price or Decimal('0')))}
            for p in by_value[:5]
        ]

        category_totals: dict = {}
        for p in products:
            key = p.category.name if p.category_id else 'Uncategorised'
            category_totals[key] = category_totals.get(key, Decimal('0')) + Decimal(p.current_stock or 0) * (p.cost_price or Decimal('0'))
        category_wise_value = [{'category': k, 'value': float(v)} for k, v in sorted(category_totals.items(), key=lambda kv: -kv[1])]

        cutoff = timezone.now() - timedelta(days=30)
        daily = (
            StockMovement.objects.filter(occurred_at__gte=cutoff)
            .annotate(day=TruncDate('occurred_at'))
            .values('day')
            .annotate(in_qty=Sum(Case(When(type__in=StockMovement.POSITIVE_TYPES, then=F('quantity')), default=Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))),
                      out_qty=Sum(Case(When(type__in=StockMovement.NEGATIVE_TYPES, then=F('quantity')), default=Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))))
            .order_by('day')
        )
        stock_movement_last_30_days = [
            {'date': str(d['day']), 'in': float(d['in_qty'] or 0), 'out': float(d['out_qty'] or 0)}
            for d in daily
        ]

        return Response({
            'total_value': float(total_value),
            'low_stock_count': len(low_stock),
            'low_stock_items': low_stock_items,
            'top_5_products_by_value': top_5_products_by_value,
            'category_wise_value': category_wise_value,
            'stock_movement_last_30_days': stock_movement_last_30_days,
        })


class StockValuationReportView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        products = products_with_stock()
        rows = [{
            'id': p.id, 'code': p.code, 'name': p.name,
            'category': p.category.name if p.category_id else None,
            'current_stock': float(p.current_stock or 0),
            'cost_price': float(p.cost_price or 0),
            'sale_price': float(p.sale_price or 0),
            'stock_value': float(Decimal(p.current_stock or 0) * (p.cost_price or Decimal('0'))),
        } for p in products]
        return Response({
            'generated_at': timezone.now().isoformat(),
            'total_stock_value': sum(r['stock_value'] for r in rows),
            'products': rows,
        })


class ProductsExportCSVView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        products = products_with_stock()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="products-{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['SKU', 'Name', 'Category', 'Unit', 'Cost Price', 'Sale Price', 'Current Stock', 'Min Stock Level', 'Barcode', 'Active'])
        for p in products:
            writer.writerow([
                p.code, p.name, p.category.name if p.category_id else '', p.unit,
                p.cost_price, p.sale_price, p.current_stock or 0, p.min_stock_level, p.barcode, p.is_active,
            ])
        return response
