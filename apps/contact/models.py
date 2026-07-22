from django.conf import settings
from django.db import models

from apps.core.validators import validate_phone_with_country_code


class ContactMessage(models.Model):
    URGENCY_CHOICES = [
        ('normal',   'Normal'),
        ('urgent',   'Urgent'),
        ('critical', 'Critical'),
    ]
    STATUS_CHOICES = [
        ('new',      'New'),
        ('reviewed', 'Reviewed'),
        ('replied',  'Replied'),
        ('closed',   'Closed'),
    ]
    PRIORITY_CHOICES = [
        ('low',    'Low'),
        ('medium', 'Medium'),
        ('high',   'High'),
    ]

    full_name  = models.CharField(max_length=200)
    email      = models.EmailField()
    phone      = models.CharField(max_length=50, blank=True, validators=[validate_phone_with_country_code])
    company    = models.CharField(max_length=200, blank=True)
    service    = models.CharField(max_length=200, blank=True)
    urgency    = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='normal')
    subject    = models.CharField(max_length=300, blank=True)
    message    = models.TextField()

    # Common qualification fields
    country         = models.CharField(max_length=50, blank=True)
    hear_about_us   = models.CharField(max_length=50, blank=True)
    industry           = models.CharField(max_length=100, blank=True)
    current_challenge  = models.CharField(max_length=200, blank=True)

    # AI-Powered ERP
    plan_interest   = models.CharField(max_length=50, blank=True)
    team_size       = models.CharField(max_length=20, blank=True)
    timeline        = models.CharField(max_length=50, blank=True)
    erp_modules     = models.CharField(max_length=500, blank=True)  # ", "-joined module names
    # Deprecated — kept for historical submissions; the contact form no longer sends these.
    budget_currency = models.CharField(max_length=10, blank=True)
    budget_range    = models.CharField(max_length=50, blank=True)

    # DevSecOps Pipelines
    tech_stack      = models.CharField(max_length=300, blank=True)
    deployment_env  = models.CharField(max_length=20, blank=True)
    num_developers  = models.CharField(max_length=20, blank=True)

    # Cloud Infrastructure
    cloud_provider    = models.CharField(max_length=20, blank=True)
    current_infra     = models.CharField(max_length=300, blank=True)
    migration_needed  = models.CharField(max_length=10, blank=True)

    # Software Development
    project_type      = models.CharField(max_length=20, blank=True)
    project_timeline   = models.CharField(max_length=20, blank=True)
    approx_budget      = models.CharField(max_length=100, blank=True)

    # AI Training & Consulting
    training_team_size   = models.CharField(max_length=20, blank=True)
    training_mode        = models.CharField(max_length=40, blank=True)
    topics_of_interest   = models.CharField(max_length=500, blank=True)
    training_duration    = models.CharField(max_length=30, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_read    = models.BooleanField(default=False)

    # Inquiry management — admin-only, never set by the public contact form.
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='new')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_inquiries',
    )
    priority    = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    notes       = models.TextField(blank=True)
    replied_at  = models.DateTimeField(null=True, blank=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} — {self.subject or 'No subject'}"
