from decimal import Decimal

from django.conf import settings
from django.db import models


class Affiliate(models.Model):
    """An affiliate application, which becomes an active affiliate once
    approved. Pending/rejected rows have no `user` yet — that account is
    created at approval time (see apps.affiliates.views.approve_affiliate),
    same pattern as apps.partners.Partner."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='affiliate',
    )

    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    # Chosen by the applicant at apply time (e.g. "LINUXFOUNDATION"), not
    # auto-generated — affiliate links need to be memorable/brandable.
    # Validated unique + uppercase-alnum in AffiliateApplySerializer.
    affiliate_code = models.CharField(max_length=20, unique=True)
    company_name = models.CharField(max_length=255, blank=True, default='')
    website = models.URLField(blank=True, default='')
    promotion_method = models.CharField(max_length=100)
    audience_size = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, default='')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'))

    total_clicks = models.IntegerField(default=0)
    total_conversions = models.IntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))

    bank_details = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.affiliate_code} ({self.full_name})"


class AffiliateClick(models.Model):
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='clicks')
    course = models.ForeignKey('lma.Course', on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    clicked_at = models.DateTimeField(auto_now_add=True)
    converted = models.BooleanField(default=False)
    # 30 days from click — the attribution window for the ?ref= cookie.
    cookie_expires = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=['affiliate', 'clicked_at'])]

    def __str__(self):
        return f"{self.affiliate.affiliate_code} click @ {self.clicked_at:%Y-%m-%d}"


class AffiliateCommission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
    ]

    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='commissions')
    enrollment = models.ForeignKey('lma.Enrollment', on_delete=models.CASCADE, related_name='affiliate_commissions')
    course = models.ForeignKey('lma.Course', on_delete=models.CASCADE)
    course_price = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['affiliate', 'enrollment']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.affiliate.affiliate_code} — {self.course.title} — ₹{self.commission_amount}"
