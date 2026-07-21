from django.conf import settings
from django.db import models

from apps.core.validators import validate_phone_with_country_code


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
    languages = models.JSONField(default=list, help_text='List of languages spoken, e.g. ["English","Arabic"]')

    current_profession = models.CharField(max_length=200)
    years_experience = models.CharField(max_length=20)
    industries = models.JSONField(default=list, help_text='List of industries with connections, e.g. ["Oil & Gas"]')
    estimated_deals = models.CharField(max_length=20)
    network_description = models.TextField()
    agreed_to_nda = models.BooleanField(default=False)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_partner_applications',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.full_name} ({self.country}) — {self.status}'
