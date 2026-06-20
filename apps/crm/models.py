"""CRM models: Customers, Leads, Contacts, Activities."""
from django.contrib.auth.models import User
from django.db import models


class Customer(models.Model):
    code = models.CharField(max_length=20, unique=True, help_text='e.g. CUST-0001')
    name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Contact(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_primary', 'name']

    def __str__(self):
        return f'{self.name} ({self.customer.name})'


class Lead(models.Model):
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
        ('other', 'Other'),
    ]
    name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE, default='website')
    status = models.CharField(max_length=20, choices=STATUS, default='new')
    estimated_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='crm_leads')
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL, related_name='leads')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Activity(models.Model):
    TYPE = [
        ('call', 'Call'),
        ('email', 'Email'),
        ('meeting', 'Meeting'),
        ('demo', 'Demo'),
        ('note', 'Note'),
    ]
    type = models.CharField(max_length=20, choices=TYPE, default='note')
    summary = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    occurred_at = models.DateTimeField()
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.CASCADE, related_name='activities')
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.CASCADE, related_name='activities')

    class Meta:
        ordering = ['-occurred_at']
        verbose_name_plural = 'Activities'

    def __str__(self):
        return f'[{self.get_type_display()}] {self.summary}'
