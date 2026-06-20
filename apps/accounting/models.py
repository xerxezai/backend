"""Accounting models: Chart of Accounts, Journal Entries."""
from django.db import models


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
