from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.validators import validate_phone_with_country_code

# Package tiers & their commission rates — shared by PartnerDeal's default commission_rate
# and the frontend's package cards / commission calculator (kept in sync manually; see
# src/partner/pages/SubmitDeal.tsx and TrainingMaterials.tsx).
PACKAGE_CHOICES = [
    ('basic', 'Basic'),
    ('professional', 'Professional'),
    ('enterprise', 'Enterprise'),
]
COMMISSION_RATES = {'basic': Decimal('10'), 'professional': Decimal('20'), 'enterprise': Decimal('30')}


def generate_partner_code() -> str:
    """XRZ-001, XRZ-002, ... — assigned once, at approval time."""
    last = Partner.objects.exclude(partner_code__isnull=True).order_by('-id').first()
    next_n = int(last.partner_code.split('-')[1]) + 1 if last and last.partner_code else 1
    return f'XRZ-{next_n:03d}'


def generate_deal_number() -> str:
    """DEAL-001, DEAL-002, ... — assigned once, at deal creation."""
    last = PartnerDeal.objects.order_by('-id').first()
    next_n = int(last.deal_number.split('-')[1]) + 1 if last and last.deal_number else 1
    return f'DEAL-{next_n:03d}'


class Partner(models.Model):
    """A partner application, which becomes an active partner once approved.
    Pending/rejected rows have no `user` yet — that account is created on approval
    (see apps.partners.views.PartnerApproveView)."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]
    COMMISSION_TIER_CHOICES = [
        ('basic', 'Basic'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='partner',
    )

    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=50, validators=[validate_phone_with_country_code])
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    target_market = models.CharField(max_length=255, blank=True, default='', help_text='Market/country they intend to sell in, e.g. "Saudi Arabia, Egypt"')
    linkedin_url = models.CharField(max_length=255, blank=True)
    languages = models.JSONField(default=list, help_text='List of languages spoken, e.g. ["English","Arabic"]')

    current_profession = models.CharField(max_length=200)
    years_experience = models.CharField(max_length=20)
    modules = models.JSONField(default=list, blank=True, help_text='Packages they applied to sell, e.g. ["Basic","Professional"]')
    estimated_deals = models.CharField(max_length=20)
    network_description = models.TextField()
    agreed_to_nda = models.BooleanField(default=False)

    commission_tier = models.CharField(max_length=20, choices=COMMISSION_TIER_CHOICES, default='basic')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    partner_code = models.CharField(max_length=20, unique=True, null=True, blank=True)

    total_deals = models.IntegerField(default=0)
    total_commission_earned = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_commission_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    notes = models.TextField(blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_partners',
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-joined_at']

    def __str__(self):
        return f'{self.full_name} ({self.country}) — {self.status}'

    def sync_stats(self):
        """Recomputes total_deals/total_commission_earned/total_commission_paid from
        this partner's deals — called after any deal is created or updated so these
        stay a correct materialized view rather than drifting counters."""
        deals = self.deals.all()
        self.total_deals = deals.count()
        self.total_commission_earned = sum((d.commission_amount or 0 for d in deals.filter(status='won')), Decimal('0'))
        self.total_commission_paid = sum((d.commission_amount or 0 for d in deals.filter(commission_status='paid')), Decimal('0'))
        self.save(update_fields=['total_deals', 'total_commission_earned', 'total_commission_paid'])


class PartnerDeal(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('reviewing', 'Reviewing'),
        ('demo_scheduled', 'Demo Scheduled'),
        ('negotiating', 'Negotiating'),
        ('won', 'Won'),
        ('lost', 'Lost'),
        ('cancelled', 'Cancelled'),
    ]
    NUM_EMPLOYEES_CHOICES = [
        ('1-10', '1-10'), ('11-50', '11-50'), ('51-200', '51-200'),
        ('201-500', '201-500'), ('500+', '500+'),
    ]
    CURRENT_SYSTEM_CHOICES = [
        ('excel', 'Currently using Excel'), ('other_erp', 'Currently using another ERP'),
        ('nothing', 'No system (manual process)'), ('other', 'Other'),
    ]
    COMMISSION_STATUS_CHOICES = [
        ('pending', 'Pending'), ('approved', 'Approved'), ('paid', 'Paid'),
    ]

    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='deals')
    deal_number = models.CharField(max_length=20, unique=True, blank=True)

    client_company = models.CharField(max_length=200)
    client_contact_person = models.CharField(max_length=200)
    client_phone = models.CharField(max_length=50, validators=[validate_phone_with_country_code])
    client_email = models.EmailField()
    client_country = models.CharField(max_length=100)

    package = models.CharField(max_length=20, choices=PACKAGE_CHOICES)
    num_employees = models.CharField(max_length=10, choices=NUM_EMPLOYEES_CHOICES)
    current_system = models.CharField(max_length=20, choices=CURRENT_SYSTEM_CHOICES)
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')

    deal_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, help_text='Filled in by XERXEZ once pricing is finalized with the client.')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text='Percent — defaults from the package (10/20/30) at submission, admin may override.')
    commission_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, help_text='Auto-calculated as deal_value * commission_rate / 100 unless set explicitly.')
    commission_status = models.CharField(max_length=10, choices=COMMISSION_STATUS_CHOICES, default='pending')
    commission_paid_at = models.DateTimeField(null=True, blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_partner_deals',
    )

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.deal_number} — {self.client_company} ({self.partner.full_name})'

    def save(self, *args, **kwargs):
        if not self.deal_number:
            self.deal_number = generate_deal_number()
        if not self.commission_rate and self.package in COMMISSION_RATES:
            self.commission_rate = COMMISSION_RATES[self.package]
        if self.deal_value and self.commission_rate and self.commission_amount is None:
            self.commission_amount = (self.deal_value * self.commission_rate / Decimal('100')).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)
