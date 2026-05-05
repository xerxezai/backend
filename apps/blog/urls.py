"""
URL configuration for Blog app
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

app_name = 'blog'
router = DefaultRouter()

# Add viewsets to router when created
# router.register('posts', BlogPostViewSet)
# router.register('categories', CategoryViewSet)
# router.register('tags', TagViewSet)

urlpatterns = [
    # Add URL patterns here
] + router.urls