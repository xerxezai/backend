"""
MLM Models for XERXEZ Backend
Implements referral tree, commission structure, and earnings tracking
Connected to Django's built-in User model
"""

import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class MLMProfile(models.Model):
    """
    Extends each User with an MLM node in the referral tree.
    Each profile knows its referrer (parent) and can look up its downline (children).
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='mlm_profile',
    )
    referrer = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='referrals',
        help_text='The MLM profile of the person who referred this user',
    )
    referral_code = models.CharField(max_length=20, unique=True, editable=False)
    level = models.PositiveIntegerField(
        default=1,
        help_text='Depth in the referral tree (1 = directly under root)',
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    total_referrals = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'MLM Profile'
        verbose_name_plural = 'MLM Profiles'
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user.username} (Level {self.level})"

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self._generate_code()
        if self.referrer:
            self.level = self.referrer.level + 1
        super().save(*args, **kwargs)

    def _generate_code(self) -> str:
        prefix = self.user.username[:4].upper() if self.user_id else 'XERX'
        return f"{prefix}{str(uuid.uuid4())[:6].upper()}"

    def get_downline(self, max_depth: int = 5):
        """Return a flat list of all descendant MLMProfiles up to max_depth levels."""
        result = []
        self._collect_downline(result, 0, max_depth)
        return result

    def _collect_downline(self, result, current_depth, max_depth):
        if current_depth >= max_depth:
            return
        for child in self.referrals.filter(is_active=True).select_related('user'):
            result.append(child)
            child._collect_downline(result, current_depth + 1, max_depth)


class CommissionStructure(models.Model):
    """
    Defines the commission percentage paid to upline members at each level.
    Level 1 = direct referrer, Level 2 = referrer's referrer, etc.
    """
    LEVEL_CHOICES = [(i, f'Level {i}') for i in range(1, 11)]

    level = models.PositiveIntegerField(
        choices=LEVEL_CHOICES,
        unique=True,
        help_text='MLM level this rate applies to (1 = direct referrer)',
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
        help_text='Commission percentage (e.g. 5.00 = 5%)',
    )
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Commission Structure'
        verbose_name_plural = 'Commission Structures'
        ordering = ['level']

    def __str__(self):
        return f"Level {self.level}: {self.commission_rate}%"


class Transaction(models.Model):
    """
    A qualifying financial transaction by a user that triggers commission calculation
    up the referral tree.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='mlm_transactions',
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    description = models.CharField(max_length=500, blank=True)
    reference = models.CharField(max_length=100, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.amount} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)


class Commission(models.Model):
    """
    A single commission record: one upline user earning from one downline transaction.
    Multiple commissions can be created per transaction (one per upline level).
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]

    earner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='commissions_earned',
        help_text='Upline user receiving this commission',
    )
    source_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='commissions_generated',
        help_text='Downline user whose transaction triggered this commission',
    )
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name='commissions',
    )
    level = models.PositiveIntegerField(
        help_text='How many levels above source_user the earner sits',
    )
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Commission'
        verbose_name_plural = 'Commissions'
        ordering = ['-created_at']
        unique_together = [['earner', 'transaction', 'level']]

    def __str__(self):
        return f"{self.earner.username} earned {self.amount} from {self.source_user.username} (L{self.level})"


class Earning(models.Model):
    """
    Aggregated earnings summary per user — updated whenever commissions change.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='mlm_earnings',
    )
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    pending_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    approved_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    last_payout = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Earning'
        verbose_name_plural = 'Earnings'

    def __str__(self):
        return f"{self.user.username} — Total: {self.total_earned}"

    def recalculate(self):
        """Recompute all earning totals from Commission records."""
        from django.db.models import Sum

        qs = Commission.objects.filter(earner=self.user)
        agg = qs.values('status').annotate(total=Sum('amount'))
        totals = {row['status']: row['total'] or Decimal('0.00') for row in agg}

        self.pending_earnings = totals.get('pending', Decimal('0.00'))
        self.approved_earnings = totals.get('approved', Decimal('0.00'))
        self.paid_earnings = totals.get('paid', Decimal('0.00'))
        self.total_earned = sum(totals.values(), Decimal('0.00'))
        self.save(update_fields=[
            'total_earned', 'pending_earnings', 'approved_earnings',
            'paid_earnings', 'updated_at',
        ])
