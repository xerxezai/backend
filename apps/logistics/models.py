"""Logistics: Shipments, Deliveries, Warehouses, Tracking."""
from django.conf import settings
from django.db import models
from apps.sales.models import SalesOrder
from apps.crm.models import Customer


def next_number(model, field, prefix):
    """Next sequential '<PREFIX>-NNN' value for a model field, based on the highest existing one."""
    last = model.objects.order_by('-id').first()
    n = 1
    val = getattr(last, field, '') if last else ''
    if val and val.startswith(prefix + '-') and val[len(prefix) + 1:].isdigit():
        n = int(val[len(prefix) + 1:]) + 1
    return f'{prefix}-{n:03d}'


class Shipment(models.Model):
    STATUS = [
        ('pending', 'Pending'),
        ('dispatched', 'Dispatched'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
    ]
    shipment_number = models.CharField(max_length=20, unique=True, help_text='e.g. SHP-001')
    tracking_number = models.CharField(max_length=60, unique=True)
    sales_order = models.ForeignKey(SalesOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name='shipments')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='shipments')
    carrier = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    origin = models.CharField(max_length=255, blank=True, help_text='Free-text origin label — auto-filled from origin_warehouse when one is selected')
    origin_warehouse = models.ForeignKey(
        'inventory.Warehouse', null=True, blank=True, on_delete=models.SET_NULL, related_name='shipments',
        help_text='Inventory warehouse this shipment originates from, if any',
    )
    destination = models.CharField(max_length=255)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    actual_delivery = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.tracking_number


class TrackingUpdate(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_updates')
    status = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']

    def __str__(self):
        return f'{self.shipment.tracking_number} - {self.status}'


class Delivery(models.Model):
    STATUS = [
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('partial', 'Partial'),
    ]
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='deliveries')
    delivery_date = models.DateField()
    delivered_by = models.CharField(max_length=150, blank=True)
    signature = models.CharField(max_length=255, blank=True, help_text='Free-text signature capture (no file upload)')
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='delivered')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-delivery_date', '-id']

    def __str__(self):
        return f'{self.shipment.tracking_number} - {self.delivery_date}'


class Warehouse(models.Model):
    """A logistics facility record — distinct from apps.inventory.Warehouse (stock-movement
    locations). Django gives each its own db_table automatically, so no collision."""
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=255, blank=True)
    capacity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    manager = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
