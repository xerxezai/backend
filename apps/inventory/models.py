"""Inventory models: products, warehouses, stock movements."""
from decimal import Decimal

from django.conf import settings
from django.db import models


class ProductCategory(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, default='')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Product categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    UNIT = [
        ('pcs', 'Pieces'),
        ('kg', 'Kilogram'),
        ('lt', 'Litre'),
        ('hr', 'Hour'),
        ('lic', 'License'),
        ('sub', 'Subscription'),
    ]
    code = models.CharField(max_length=30, unique=True, help_text='SKU')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(ProductCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name='products')
    unit = models.CharField(max_length=10, choices=UNIT, default='pcs')
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_digital = models.BooleanField(default=False, help_text='True for digital/SaaS products')
    is_active = models.BooleanField(default=True)
    reorder_level = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_stock_level = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    barcode = models.CharField(max_length=64, blank=True, default='')
    image = models.ImageField(upload_to='products/', null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Warehouse(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=255, blank=True)
    capacity = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Maximum total unit capacity, 0 = unlimited')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class StockMovement(models.Model):
    TYPE = [
        ('in', 'Receipt'),
        ('out', 'Issue'),
        ('transfer', 'Transfer'),
        ('adjust', 'Adjustment'),
        ('return', 'Return'),
        ('damage', 'Damage'),
    ]
    # Sign convention — single source of truth, used both for the SQL Case expression
    # in ProductViewSet/WarehouseViewSet and the Python-side sum in StockMovementSerializer.
    # 'transfer' is intentionally neutral: warehouse-to-warehouse transfers are recorded as
    # a paired 'out' (source) + 'in' (destination), which already nets correctly on its own.
    POSITIVE_TYPES = ('in', 'adjust', 'return')
    NEGATIVE_TYPES = ('out', 'damage')

    type = models.CharField(max_length=10, choices=TYPE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_movements')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='stock_movements')
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=120, blank=True)
    reason = models.CharField(max_length=200, blank=True, default='')
    occurred_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='stock_movements_created')

    class Meta:
        ordering = ['-occurred_at']

    def __str__(self):
        return f'{self.get_type_display()} {self.product} x {self.quantity}'

    @property
    def signed_quantity(self) -> Decimal:
        if self.type in self.POSITIVE_TYPES:
            return self.quantity
        if self.type in self.NEGATIVE_TYPES:
            return -self.quantity
        return Decimal('0')
