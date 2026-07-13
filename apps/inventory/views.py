from rest_framework import viewsets, filters
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Case, When, F, Value, DecimalField
from django.db.models.functions import Coalesce

from .models import ProductCategory, Product, Warehouse, StockMovement
from .serializers import ProductCategorySerializer, ProductSerializer, WarehouseSerializer, StockMovementSerializer


class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code']


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'code', 'description']
    filterset_fields = ['category', 'is_active', 'is_digital', 'unit']

    def get_queryset(self):
        # current_stock = receipts + adjustments - issues, summed across all warehouses.
        # 'transfer' moves stock between warehouses without changing the product's total, so it's excluded.
        stock_delta = Case(
            When(stock_movements__type__in=['in', 'adjust'], then=F('stock_movements__quantity')),
            When(stock_movements__type='out', then=-F('stock_movements__quantity')),
            default=Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        return Product.objects.select_related('category').annotate(
            current_stock=Coalesce(Sum(stock_delta), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
        ).order_by('name')


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code']


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.select_related('product', 'warehouse').all()
    serializer_class = StockMovementSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['type', 'product', 'warehouse']
    ordering_fields = ['occurred_at']
