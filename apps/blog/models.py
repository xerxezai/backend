"""
Blog models for SEOZ Backend
Handles blog posts, categories, and comments with SEO optimization
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from apps.core.models import BaseModel, SEOMetadata, PublishableModel, SoftDeleteModel


class Category(BaseModel):
    """
    Blog category model
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff')  # Hex color
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name


class Tag(BaseModel):
    """
    Blog tag model
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)
    
    class Meta:
        ordering = ['name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name


class BlogPost(PublishableModel, SEOMetadata, SoftDeleteModel):
    """
    Blog post model with SEO and publishing capabilities
    """
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    content = models.TextField()
    excerpt = models.TextField(max_length=300, blank=True)
    featured_image = models.ImageField(upload_to='blog/featured/', blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    read_time = models.PositiveIntegerField(default=0)  # in minutes
    
    # Content flags
    is_featured = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-publish_date', '-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_published', 'publish_date']),
            models.Index(fields=['category']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        
        # Auto-generate excerpt from content if not provided
        if not self.excerpt and self.content:
            self.excerpt = self.content[:297] + '...' if len(self.content) > 300 else self.content
        
        # Estimate read time (average 200 words per minute)
        word_count = len(self.content.split())
        self.read_time = max(1, word_count // 200)
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.title
    
    @property
    def is_published_now(self):
        """Check if post is currently published"""
        if not self.is_published:
            return False
        if self.publish_date:
            from django.utils import timezone
            return self.publish_date <= timezone.now()
        return True


class Comment(BaseModel, SoftDeleteModel):
    """
    Blog comment model
    """
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    author_name = models.CharField(max_length=100)
    author_email = models.EmailField()
    author_website = models.URLField(blank=True)
    content = models.TextField()
    
    # Moderation
    is_approved = models.BooleanField(default=False)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', 'is_approved']),
        ]
    
    def __str__(self):
        return f'Comment by {self.author_name} on {self.post.title}'