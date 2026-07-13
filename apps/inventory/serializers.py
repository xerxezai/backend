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

    class Meta:
        model = ProductCategory
        fields = '__all__'

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

    class Meta:
        model = Warehouse
        fields = '__all__'

    def create(self, validated_data):
        if not validated_data.get('code'):
            validated_data['code'] = _gen_code(Warehouse, 'WH')
        return super().create(validated_data)


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    occurred_at = serializers.DateTimeField(required=False, default=timezone.now)

    class Meta:
        model = StockMovement
        fields = '__all__'
