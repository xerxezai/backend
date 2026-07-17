"""Accounting models: Chart of Accounts, Journal Entries, Expenses, Tax Reports."""
from django.conf import settings
from django.db import models


def next_number(model, field, prefix):
    """Next sequential '<PREFIX>-NNN' value for a model field, based on the highest existing one.
    Copied verbatim from apps.procurement.models — kept local so this app doesn't cross-import."""
    last = model.objects.order_by('-id').first()
    n = 1
    val = getattr(last, field, '') if last else ''
    if val and val.startswith(prefix + '-') and val[len(prefix) + 1:].isdigit():
        n = int(val[len(prefix) + 1:]) + 1
    return f'{prefix}-{n:03d}'


class Account(models.Model):
    TYPE = [
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity'),
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    code = models.CharField(max_length=20, unique=True, help_text='e.g. 1000, 1100')
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPE)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class JournalEntry(models.Model):
    number = models.CharField(max_length=20, unique=True, help_text='e.g. JE-0001')
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    posted = models.BooleanField(default=False)
    reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        verbose_name_plural = 'Journal entries'

    def __str__(self):
        return self.number

    @property
    def is_balanced(self):
        debit = sum((l.debit for l in self.lines.all()), 0)
        credit = sum((l.credit for l in self.lines.all()), 0)
        return debit == credit


class JournalLine(models.Model):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='journal_lines')
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f'{self.account} D:{self.debit} C:{self.credit}'


class Expense(models.Model):
    STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    expense_number = models.CharField(max_length=20, unique=True, help_text='e.g. EXP-001')
    category = models.CharField(max_length=100, help_text='Free text, e.g. "Travel", "Office Supplies"')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    paid_by = models.CharField(max_length=150, blank=True, help_text='Free-text name of who paid')
    receipt_image = models.ImageField(upload_to='receipts/', null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_expenses',
        help_text='Who created this record — drives RBAC data-level filtering for Regular User/Read Only roles.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return self.expense_number


class TaxReport(models.Model):
    """Saved/snapshotted tax report rows. The live GET /accounting/tax-report/ endpoint computes
    figures on the fly from Invoice/PurchaseOrder data and does not require a row here to exist."""
    period = models.CharField(max_length=20, help_text='e.g. "2026-07" (monthly) or "2026-Q3" (quarterly)')
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_tax_collected = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_tax_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-period']

    def __str__(self):
        return f'Tax Report {self.period}'
