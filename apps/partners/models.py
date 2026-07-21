import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.validators import validate_phone_with_country_code

# Package tiers & their commission rates — shared by PartnerLead.commission_amount and the
# frontend's commission calculator/reference sections (kept in sync manually; see
# src/components/erp/partners/PartnerPortal constants).
PACKAGE_CHOICES = [
    ('basic', 'Basic'),
    ('professional', 'Professional'),
    ('enterprise', 'Enterprise'),
]
COMMISSION_RATES = {'basic': Decimal('10'), 'professional': Decimal('20'), 'enterprise': Decimal('30')}


class PartnerApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewing', 'Reviewing'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=50, validators=[validate_phone_with_country_code])
    linkedin_url = models.CharField(max_length=255, blank=True)

    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    target_market = models.CharField(max_length=255, blank=True, default='', help_text='Market/country they intend to sell in, e.g. "Saudi Arabia, Egypt"')
    languages = models.JSONField(default=list, help_text='List of languages spoken, e.g. ["English","Arabic"]')

    current_profession = models.CharField(max_length=200)
    years_experience = models.CharField(max_length=20)
    modules = models.JSONField(default=list, blank=True, help_text='List of XERXEZ modules they can sell, e.g. ["CRM (Customer Management)","Full ERP Suite (All Modules)"]')
    estimated_deals = models.CharField(max_length=20)
    network_description = models.TextField()
    agreed_to_nda = models.BooleanField(default=False)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_partner_applications',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    # Set once, the first time this application is approved — the Partner Portal login
    # credential (paired with email) is this token, not a Django user account/password.
    portal_token = models.CharField(max_length=64, blank=True, default='', db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.full_name} ({self.country}) — {self.status}'

    def ensure_portal_token(self):
        """Generates and saves a portal_token if one doesn't exist yet — idempotent, so
        re-approving (or PUTting notes on) an already-approved application never rotates
        the partner's existing login credential out from under them."""
        if not self.portal_token:
            self.portal_token = secrets.token_urlsafe(24)
            self.save(update_fields=['portal_token'])
        return self.portal_token


class PartnerLead(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('contacted', 'Contacted'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    ]

    partner = models.ForeignKey(PartnerApplication, on_delete=models.CASCADE, related_name='leads')

    client_name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    country = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)

    package = models.CharField(max_length=20, choices=PACKAGE_CHOICES)
    modules_needed = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)

    deal_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, help_text='Deal value once known — commission is computed from this, not stored separately.')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='submitted')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.client_name} ({self.package}) — {self.partner.full_name}'

    @property
    def commission_amount(self) -> Decimal:
        if not self.deal_value or self.package not in COMMISSION_RATES:
            return Decimal('0')
        return (self.deal_value * COMMISSION_RATES[self.package] / Decimal('100')).quantize(Decimal('0.01'))
