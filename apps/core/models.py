"""
Core models for SEOZ Backend
Base models with common functionality using soft coding principles
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
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
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                 null=True, blank=True, related_name='+')
    
    class Meta:
        abstract = True