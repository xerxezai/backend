"""
Core models for XERXEZ Backend
Base models with common functionality using soft coding principles
"""

from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid


class BaseModel(models.Model):
    """
    Abstract base model with common fields
    Implements soft coding for consistent structure
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        abstract = True
        ordering = ['-created_at']


class SEOMetadata(models.Model):
    """
    SEO metadata model for content
    Reusable across different content types
    """
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(max_length=160, blank=True)
    keywords = models.CharField(max_length=255, blank=True)
    og_title = models.CharField(max_length=255, blank=True)
    og_description = models.TextField(max_length=160, blank=True)
    og_image = models.ImageField(upload_to='seo/og_images/', blank=True, null=True)
    
    class Meta:
        abstract = True


class PublishableModel(BaseModel):
    """
    Abstract model for publishable content
    """
    is_published = models.BooleanField(default=False)
    publish_date = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Abstract model for soft deletion
    """
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='+')

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Security audit trail — login/logout events across every login surface
    (ERP, LMA, Partner Portal). `username` is stored as plain text rather than
    a FK so a failed login attempt against a non-existent username is still
    recorded (there's no User row to point a FK at). Admin panel CRUD actions
    are already logged by Django's own django.contrib.admin.models.LogEntry —
    this model deliberately doesn't duplicate that, it only covers auth events,
    which LogEntry has no concept of."""
    ACTION_CHOICES = [
        ('login_success', 'Login succeeded'),
        ('login_failure', 'Login failed'),
        ('logout',        'Logout'),
    ]

    action     = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    username   = models.CharField(max_length=150, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    source     = models.CharField(max_length=20, blank=True, help_text="erp / lma / partner")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} — {self.username or 'unknown'} @ {self.ip_address} ({self.created_at:%Y-%m-%d %H:%M})"