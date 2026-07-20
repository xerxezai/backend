"""CRM models: Customers, Leads, Contacts, Activities."""
from django.conf import settings
from django.db import models

from apps.core.validators import validate_phone_with_country_code


class Customer(models.Model):
    # Named `tenant`, not `company` (unlike every other model's FK), because Customer
    # already has a pre-existing `company` CharField below for the customer's own
    # free-text company name (e.g. "Infosys Ltd") — reusing the name would silently
    # shadow this FK. RBACScopedMixin.company_field is overridden to 'tenant' for this
    # viewset accordingly.
    tenant = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    SOURCE = [
        ('website', 'Website'),
        ('referral', 'Referral'),
        ('outbound', 'Outbound'),
        ('event', 'Event'),
        ('social', 'Social Media'),
        ('email', 'Email'),
        ('other', 'Other'),
    ]
    code = models.CharField(max_length=20, unique=True, help_text='e.g. CUST-0001')
    name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True, validators=[validate_phone_with_country_code])
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE, blank=True, default='')
    tags = models.JSONField(default=list, blank=True, help_text='e.g. ["VIP","Prospect"]')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_customers',
        help_text='Who created this record — drives RBAC data-level filtering for Regular User/Read Only roles.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Contact(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True, validators=[validate_phone_with_country_code])
    is_primary = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )

    class Meta:
        ordering = ['-is_primary', 'name']

    def __str__(self):
        return f'{self.name} ({self.customer.name})'


class Lead(models.Model):
    # See Customer.tenant — same CharField collision (Lead also has a free-text
    # `company` field below).
    tenant = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    STATUS = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('proposal', 'Proposal Sent'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    ]
    SOURCE = [
        ('website', 'Website'),
        ('referral', 'Referral'),
        ('outbound', 'Outbound'),
        ('event', 'Event'),
        ('social', 'Social Media'),
        ('email', 'Email'),
        ('other', 'Other'),
    ]
    SCORE = [
        ('hot', 'Hot'),
        ('warm', 'Warm'),
        ('cold', 'Cold'),
    ]
    name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True, validators=[validate_phone_with_country_code])
    source = models.CharField(max_length=20, choices=SOURCE, default='website')
    score = models.CharField(max_length=10, choices=SCORE, default='warm')
    status = models.CharField(max_length=20, choices=STATUS, default='new')
    estimated_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    follow_up_date = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='crm_leads')
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL, related_name='leads')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_leads',
        help_text='Who created this record — drives RBAC data-level filtering for Regular User/Read Only roles.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Activity(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    TYPE = [
        ('call', 'Call'),
        ('email', 'Email'),
        ('meeting', 'Meeting'),
        ('demo', 'Demo'),
        ('task', 'Task'),
        ('follow_up', 'Follow Up'),
        ('note', 'Note'),
    ]
    type = models.CharField(max_length=20, choices=TYPE, default='note')
    summary = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    occurred_at = models.DateTimeField()
    due_date = models.DateField(null=True, blank=True, help_text='For task-type activities — when it is due')
    completed = models.BooleanField(default=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.CASCADE, related_name='activities')
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.CASCADE, related_name='activities')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )

    class Meta:
        ordering = ['-occurred_at']
        verbose_name_plural = 'Activities'

    def __str__(self):
        return f'[{self.get_type_display()}] {self.summary}'


class Deal(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    STAGE_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('proposal', 'Proposal Sent'),
        ('negotiation', 'Negotiation'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    ]
    title = models.CharField(max_length=200)
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='deals', null=True, blank=True
    )
    lead = models.ForeignKey(
        'Lead', on_delete=models.CASCADE,
        related_name='deals', null=True, blank=True
    )
    value = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    stage = models.CharField(
        max_length=20, choices=STAGE_CHOICES, default='new'
    )
    probability = models.PositiveSmallIntegerField(
        default=0, help_text='Win probability, 0-100'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True
    )
    expected_close = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crm_deal'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.get_stage_display()})'


class CustomerNote(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    NOTE_TYPE_CHOICES = [
        ('call', 'Phone Call'),
        ('meeting', 'Meeting'),
        ('email', 'Email'),
        ('follow_up', 'Follow Up'),
        ('general', 'General Note'),
    ]
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='notes', null=True, blank=True
    )
    lead = models.ForeignKey(
        'Lead', on_delete=models.CASCADE,
        related_name='note_entries', null=True, blank=True
    )
    note_type = models.CharField(
        max_length=20, choices=NOTE_TYPE_CHOICES,
        default='general'
    )
    content = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crm_customer_note'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_note_type_display()}] {self.content[:40]}'
