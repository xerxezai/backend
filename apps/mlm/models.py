"""MLM: 3-level Distributor network, order-driven Commission, Payout, MLMSettings."""
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


def next_number(model, field, prefix):
    """Next sequential '<PREFIX>-NNN' value for a model field, based on the highest existing one."""
    last = model.objects.order_by('-id').first()
    n = 1
    val = getattr(last, field, '') if last else ''
    if val and val.startswith(prefix + '-') and val[len(prefix) + 1:].isdigit():
        n = int(val[len(prefix) + 1:]) + 1
    return f'{prefix}-{n:03d}'


class Distributor(models.Model):
    STATUS = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='distributor_profile',
        help_text='Optional login account — not every distributor row needs one',
    )
    distributor_id = models.CharField(max_length=20, unique=True, help_text='e.g. DIST-001')
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    sponsor = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='downline', help_text='Who referred this distributor; null = root/top-level',
    )
    level = models.PositiveSmallIntegerField(default=1, help_text='1, 2 or 3 — computed from sponsor.level + 1, capped at 3')
    status = models.CharField(max_length=10, choices=STATUS, default='active')
    joining_date = models.DateField(default=timezone.localdate)
    total_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0, help_text='Denormalized — updated when commissions are calculated')
    total_earnings = models.DecimalField(max_digits=14, decimal_places=2, default=0, help_text='Denormalized sum of this distributor\'s commission amounts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.distributor_id} — {self.name}'

    def save(self, *args, **kwargs):
        if self.sponsor_id:
            self.level = min((self.sponsor.level or 1) + 1, 3)
        else:
            self.level = 1
        super().save(*args, **kwargs)

    def get_downline(self, max_depth: int = 3):
        """Flat list of all descendant Distributors up to max_depth levels."""
        result = []
        self._collect_downline(result, 0, max_depth)
        return result

    def _collect_downline(self, result, current_depth, max_depth):
        if current_depth >= max_depth:
            return
        for child in self.downline.all():
            result.append(child)
            child._collect_downline(result, current_depth + 1, max_depth)


class Commission(models.Model):
    STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
    ]
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE, related_name='commissions', help_text='The earner')
    order = models.ForeignKey('sales.SalesOrder', null=True, blank=True, on_delete=models.CASCADE, related_name='mlm_commissions', help_text='Null for manually-added commissions not tied to a sales order')
    level = models.PositiveSmallIntegerField(help_text='1, 2 or 3 — how many levels above the order\'s originating distributor this earner sits')
    rate = models.DecimalField(max_digits=5, decimal_places=2, help_text='Percentage, e.g. 10.00')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    notes = models.TextField(blank=True, default='')
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_date']

    def __str__(self):
        return f'{self.distributor} earned {self.amount} (L{self.level}) from {self.order}'


class Payout(models.Model):
    STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
    ]
    METHOD = [
        ('bank', 'Bank'),
        ('upi', 'UPI'),
        ('cash', 'Cash'),
    ]
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE, related_name='payouts')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payout_date = models.DateField()
    method = models.CharField(max_length=10, choices=METHOD, default='bank')
    reference_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payout_date', '-id']

    def __str__(self):
        return f'Payout {self.id} — {self.distributor} ({self.amount})'


class MLMSettings(models.Model):
    """Singleton config row — always pk=1, fetched via get_solo()."""
    level1_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))
    level2_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    level3_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('2.00'))

    class Meta:
        verbose_name = 'MLM Settings'
        verbose_name_plural = 'MLM Settings'

    def __str__(self):
        return 'MLM Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
