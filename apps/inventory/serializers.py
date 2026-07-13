from decimal import Decimal

from rest_framework import serializers
from .models import ProductCategory, Product, Warehouse, StockMovement
from django.utils import timezone


def _gen_code(model, prefix, pad=3):
    n = model.objects.count()
    while True:
        code = f"{prefix}{str(n + 1).zfill(pad)}"
        if not model.objects.filter(code=code).exists():
            return code
        n += 1


class ProductCategorySerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, allow_blank=True)
    product_count = serializers.SerializerMethodField()
    total_stock_value = serializers.SerializerMethodField()

    class Meta:
        model = ProductCategory
        fields = '__all__'

    def get_product_count(self, obj):
        return obj.products.count()

    def get_total_stock_value(self, obj):
        total = Decimal('0')
        for p in obj.products.prefetch_related('stock_movements'):
            stock = sum((m.signed_quantity for m in p.stock_movements.all()), Decimal('0'))
            total += stock * (p.cost_price or Decimal('0'))
        return total

    def create(self, validated_data):
        if not validated_data.get('code', '').strip():
            validated_data['code'] = _gen_code(ProductCategory, 'CAT')
        return super().create(validated_data)


class ProductSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, allow_blank=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    current_stock = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = '__all__'

    def get_current_stock(self, obj):
        return getattr(obj, 'current_stock', None) or 0

    def get_is_low_stock(self, obj):
        stock = getattr(obj, 'current_stock', None) or 0
        return stock < (obj.min_stock_level or 0)

    def create(self, validated_data):
        if not validated_data.get('code', '').strip():
            validated_data['code'] = _gen_code(Product, 'PROD')
        return super().create(validated_data)


class WarehouseSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, allow_blank=True)
    current_stock_units = serializers.SerializerMethodField()
    current_stock_value = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = '__all__'

    def get_current_stock_units(self, obj):
        return sum((m.signed_quantity for m in obj.stock_movements.all()), Decimal('0'))

    def get_current_stock_value(self, obj):
        total = Decimal('0')
        for m in obj.stock_movements.select_related('product').all():
            total += m.signed_quantity * (m.product.cost_price or Decimal('0'))
        return total

    def create(self, validated_data):
        if not validated_data.get('code'):
            validated_data['code'] = _gen_code(Warehouse, 'WH')
        return super().create(validated_data)


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    occurred_at = serializers.DateTimeField(required=False, default=timezone.now)

    class Meta:
        model = StockMovement
        fields = '__all__'
        read_only_fields = ['created_by']

    def get_created_by_name(self, obj):
        if not obj.created_by_id:
            return None
        return obj.created_by.get_full_name() or obj.created_by.username
