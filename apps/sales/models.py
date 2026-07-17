"""Sales models: Quotations and Sales Orders."""
from decimal import Decimal
from django.conf import settings
from django.db import models

from apps.crm.models import Customer

GST_RATE = Decimal('0.18')


class Quotation(models.Model):
    STATUS = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    number = models.CharField(max_length=20, unique=True, help_text='e.g. QUO-0001')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='quotations')
    issue_date = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='draft')
    notes = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-issue_date', '-id']

    def __str__(self):
        return self.number

    def recalc(self):
        """Recompute subtotal/tax/total from line items. Tax is 18% GST on the subtotal."""
        sub = sum((i.line_total for i in self.items.all()), Decimal('0'))
        self.subtotal = sub
        self.tax = (sub * GST_RATE).quantize(Decimal('0.01'))
        self.total = self.subtotal + self.tax


class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('inventory.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='quotation_items')
    description = models.CharField(max_length=255, blank=True, help_text='Free-text line description; defaults to the product name')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        if not self.description and self.product_id:
            self.description = self.product.name
        self.line_total = (self.quantity or 0) * (self.unit_price or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.description} x {self.quantity}'


class SalesOrder(models.Model):
    STATUS = [
        ('open', 'Open'),
        ('confirmed', 'Confirmed'),
        ('fulfilled', 'Fulfilled'),
        ('cancelled', 'Cancelled'),
    ]
    number = models.CharField(max_length=20, unique=True, help_text='e.g. SO-0001')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='sales_orders')
    quotation = models.ForeignKey(Quotation, null=True, blank=True, on_delete=models.SET_NULL, related_name='orders')
    salesperson = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='sales_orders_assigned')
    distributor = models.ForeignKey(
        'mlm.Distributor', null=True, blank=True, on_delete=models.SET_NULL, related_name='sales_orders_as_salesperson',
        help_text='MLM distributor credited as salesperson for this order, if any — mutually exclusive with salesperson in the UI',
    )
    order_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS, default='open')
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_sales_orders',
        help_text='Who created this record — drives RBAC data-level filtering for Regular User/Read Only roles.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-order_date', '-id']

    def __str__(self):
        return self.number

    def recalc(self):
        """Recompute subtotal/tax/total from line items. Tax is 18% GST on the subtotal —
        matches Quotation.recalc() so an order's total always equals what an auto-generated
        invoice for it will show (previously this omitted GST entirely, so an invoice
        generated from an order came out ~18% higher than the order's own total).
        Only called when items are explicitly managed via the serializer — orders without
        items keep whatever total was set directly (e.g. quotation conversion), so this
        never zeroes out legacy data."""
        sub = sum((i.line_total for i in self.items.all()), Decimal('0'))
        self.subtotal = sub
        self.tax = (sub * GST_RATE).quantize(Decimal('0.01'))
        self.total = self.subtotal + self.tax


class SalesOrderItem(models.Model):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('inventory.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='sales_order_items')
    description = models.CharField(max_length=255, blank=True, help_text='Free-text line description; defaults to the product name')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        if not self.description and self.product_id:
            self.description = self.product.name
        self.line_total = (self.quantity or 0) * (self.unit_price or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.description} x {self.quantity}'
