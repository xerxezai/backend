from django.db import models
from apps.core.models import BaseModel, PublishableModel, SEOMetadata


class Service(PublishableModel, SEOMetadata):
    """
    A service offered by the company (e.g. "SEO Optimization", "Web Design")
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True, help_text="Icon name or class, e.g. 'seo-icon'")
    image = models.ImageField(upload_to='services/images/', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    order = models.PositiveIntegerField(default=0, help_text="Controls display order on the site")

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.name
