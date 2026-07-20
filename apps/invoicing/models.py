"""Invoicing & Payments models."""
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.crm.models import Customer
from apps.sales.models import SalesOrder

GST_RATE = Decimal('0.18')


def add_months(d, months):
    """Month-safe date addition with no external dependency (dateutil isn't in requirements.txt)."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return d.replace(year=year, month=month, day=day)


class Invoice(models.Model):
    STATUS = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    number = models.CharField(max_length=20, unique=True, help_text='e.g. INV-0001')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
    sales_order = models.ForeignKey(SalesOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name='invoices')
    issue_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS, default='draft')
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issue_date', '-id']

    def __str__(self):
        return self.number

    @property
    def balance(self):
        return (self.total or Decimal('0')) - (self.amount_paid or Decimal('0'))

    def recalc(self):
        """Recompute subtotal/tax/total from line items. Tax is 18% GST on the subtotal."""
        sub = sum((i.line_total for i in self.items.all()), Decimal('0'))
        self.subtotal = sub
        self.tax = (sub * GST_RATE).quantize(Decimal('0.01'))
        self.total = self.subtotal + self.tax


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('inventory.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='invoice_items')
    description = models.CharField(max_length=255, blank=True, help_text='Free-text line description; defaults to the product name')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        if not self.description and self.product_id:
            self.description = self.product.name
        self.line_total = (self.quantity or 0) * (self.unit_price or 0)
        super().save(*args, **kwargs)


class Payment(models.Model):
    METHOD = [
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('card', 'Card'),
        ('upi', 'UPI'),
        ('cheque', 'Cheque'),
        ('online', 'Online Gateway'),
        ('credit_note', 'Credit Note'),
        ('other', 'Other'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD, default='bank')
    reference = models.CharField(max_length=120, blank=True)
    paid_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )

    class Meta:
        ordering = ['-paid_at']

    def __str__(self):
        return f'{self.invoice.number} - {self.amount}'


class RecurringInvoice(models.Model):
    FREQUENCY = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    ]
    STATUS = [
        ('active', 'Active'),
        ('paused', 'Paused'),
    ]
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='recurring_invoices')
    description = models.CharField(max_length=255, blank=True, help_text='Line description on generated invoices, e.g. "Monthly retainer"')
    amount = models.DecimalField(max_digits=14, decimal_places=2, help_text='Pre-tax line amount; 18% GST is added on the generated invoice, same as a manual invoice')
    frequency = models.CharField(max_length=10, choices=FREQUENCY, default='monthly')
    next_due_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS, default='active')
    last_generated_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['next_due_date']

    def __str__(self):
        return f'{self.customer.name} — {self.get_frequency_display()} ({self.amount})'

    def advance_next_due_date(self):
        if self.frequency == 'weekly':
            self.next_due_date = self.next_due_date + timedelta(days=7)
        elif self.frequency == 'quarterly':
            self.next_due_date = add_months(self.next_due_date, 3)
        else:
            self.next_due_date = add_months(self.next_due_date, 1)

    def generate_invoice(self):
        """Creates a real Invoice (+ single InvoiceItem) from this template, and advances
        next_due_date by one frequency period. Generated invoices start as 'draft' — deliberately
        not auto-sent, so a human reviews before it goes to the customer."""
        last = Invoice.objects.order_by('-id').first()
        next_n = 1
        if last and last.number.startswith('INV-') and last.number[4:].isdigit():
            next_n = int(last.number[4:]) + 1
        today = timezone.now().date()
        invoice = Invoice.objects.create(
            number=f'INV-{next_n:03d}',
            customer=self.customer,
            issue_date=today,
            due_date=today + timedelta(days=30),
            status='draft',
            notes=f'Auto-generated from recurring invoice #{self.id} ({self.get_frequency_display()}).',
            created_by=self.created_by,  # generated invoices belong to the template's owner
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            description=self.description or f'{self.get_frequency_display()} charge',
            quantity=1,
            unit_price=self.amount,
        )
        invoice.recalc()
        invoice.save()
        self.last_generated_at = timezone.now()
        self.advance_next_due_date()
        self.save(update_fields=['last_generated_at', 'next_due_date'])
        return invoice


class CreditNote(models.Model):
    STATUS = [
        ('issued', 'Issued'),
        ('applied', 'Applied'),
        ('cancelled', 'Cancelled'),
    ]
    number = models.CharField(max_length=20, unique=True, help_text='e.g. CN-001')
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='credit_notes')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='credit_notes')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS, default='issued')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return self.number

    def apply(self):
        """Applies this credit note to its invoice by recording it in the same Payment
        ledger real payments use, so amount_paid/status stay derived from one source of
        truth (see sync_invoice_payment_status in views.py) instead of a parallel path."""
        from .views import sync_invoice_payment_status  # local import avoids a views<->models circular import
        if self.status == 'applied':
            raise ValueError('This credit note has already been applied.')
        Payment.objects.create(
            invoice=self.invoice, amount=self.amount, method='credit_note',
            reference=self.number, paid_at=timezone.now(),
            notes=f'Credit note {self.number}' + (f': {self.reason}' if self.reason else ''),
        )
        sync_invoice_payment_status(self.invoice)
        self.status = 'applied'
        self.save(update_fields=['status'])
