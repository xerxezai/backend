from django.conf import settings
from django.db import models


class Company(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('trial', 'Trial'),
        ('suspended', 'Suspended'),
    ]
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    industry = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='UAE')
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    plan = models.CharField(max_length=50, default='basic')
    max_users = models.IntegerField(default=10, help_text='Maximum number of users allowed for this company')
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['name']

    def __str__(self):
        return self.name


class CompanyUser(models.Model):
    ROLE_CHOICES = [
        ('company_admin', 'Company Admin'),
        ('module_admin', 'Module Admin'),
        ('regular_user', 'Regular User'),
        ('read_only', 'Read Only'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='company_users')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='company_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='regular_user')
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'user']

    def __str__(self):
        return f'{self.user} at {self.company}'
