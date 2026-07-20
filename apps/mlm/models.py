"""MLM: 3-level Distributor network, order-driven Commission, Payout, MLMSettings."""
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import Sum
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
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
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
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
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
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
    ]
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE, related_name='commissions', help_text='The earner')
    order = models.ForeignKey('sales.SalesOrder', null=True, blank=True, on_delete=models.CASCADE, related_name='mlm_commissions', help_text='Null for manually-added commissions not tied to a sales order')
    level = models.PositiveSmallIntegerField(help_text='1, 2 or 3 — how many levels above the order\'s originating distributor this earner sits')
    rate = models.DecimalField(max_digits=5, decimal_places=2, help_text='Percentage, e.g. 10.00')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_date']

    def __str__(self):
        return f'{self.distributor} earned {self.amount} (L{self.level}) from {self.order}'


def _recalc_distributor_totals(distributor):
    """Recomputes total_sales/total_earnings from the distributor's actual commission and
    order records, rather than incrementing them — so a later change to an order's total
    (e.g. editing its line items) can't leave these denormalized figures stale or drifted."""
    earnings = Commission.objects.filter(distributor=distributor).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    sales = distributor.sales_orders_as_salesperson.filter(status='confirmed').aggregate(t=Sum('total'))['t'] or Decimal('0')
    Distributor.objects.filter(pk=distributor.pk).update(total_earnings=earnings, total_sales=sales)


def generate_commission_for_order(order):
    """Creates or updates the Pending commission for order.distributor — the MLM distributor
    assigned as a SalesOrder's salesperson — based on that distributor's own level rate from
    MLMSettings. Called from apps.sales.views whenever a SalesOrder is saved in 'confirmed'
    status with a distributor assigned (it's called after every save rather than needing precise
    'did status/total just change' tracking across the three code paths that can change a
    SalesOrder — create, update, and the dedicated status action).

    A zero (or negative) order total never gets a commission: an existing zero-amount pending
    commission is removed, and no new one is created. Otherwise, if a commission already exists
    for this order+distributor pair, its rate/amount are refreshed to match the order's current
    total (so editing line items after confirmation keeps the commission correct) — unless it's
    already been paid, which is left untouched since it's settled."""
    if not order.distributor_id:
        return None

    distributor = order.distributor
    settings_obj = MLMSettings.get_solo()
    rate_by_level = {1: settings_obj.level1_rate, 2: settings_obj.level2_rate, 3: settings_obj.level3_rate}
    rate = rate_by_level.get(distributor.level, Decimal('0'))
    amount = (order.total or Decimal('0')) * (rate / Decimal('100'))

    existing = Commission.objects.filter(order_id=order.id, distributor_id=order.distributor_id).first()

    if amount <= 0:
        if existing and existing.status != 'paid':
            existing.delete()
            _recalc_distributor_totals(distributor)
        return None

    if existing:
        if existing.status == 'paid':
            return existing
        if existing.rate != rate or existing.amount != amount:
            existing.rate = rate
            existing.amount = amount
            existing.save(update_fields=['rate', 'amount'])
            _recalc_distributor_totals(distributor)
        return existing

    commission = Commission.objects.create(
        distributor=distributor, order=order, level=distributor.level, rate=rate, amount=amount, status='pending',
        # Auto-generated commissions belong to whoever owns the originating sales order,
        # so the same user keeps seeing them under the own-data-only rule.
        created_by=order.created_by,
    )
    _recalc_distributor_totals(distributor)
    return commission


class Payout(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
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
    commission = models.OneToOneField(
        Commission, null=True, blank=True, on_delete=models.SET_NULL, related_name='payout',
        help_text='The commission this payout was auto-created from, on approval. Null for '
                   'manually-created payouts (e.g. one payout bundling several commissions).',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payout_date = models.DateField()
    method = models.CharField(max_length=10, choices=METHOD, default='bank')
    reference_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default='pending')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payout_date', '-id']

    def __str__(self):
        return f'Payout {self.id} — {self.distributor} ({self.amount})'


def generate_payout_for_commission(commission: 'Commission'):
    """Books one pending Payout the first time a Commission is approved — idempotent via the
    OneToOneField (a second call for an already-paid-out commission is a no-op), mirroring
    generate_commission_for_order's create-or-return-existing shape. A zero/negative-amount
    commission never gets a payout, same guard as the zero-total case in commission generation."""
    if commission.status != 'approved' or commission.amount <= 0:
        return None
    existing = Payout.objects.filter(commission=commission).first()
    if existing:
        return existing
    return Payout.objects.create(
        distributor=commission.distributor, commission=commission, amount=commission.amount,
        payout_date=timezone.now().date(), status='pending',
        created_by=commission.created_by,  # payout follows its commission's owner
    )


class MLMSettings(models.Model):
    """Singleton config row — always pk=1, fetched via get_solo()."""
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
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
