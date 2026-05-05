"""
URL configuration for Projects app
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

app_name = 'projects'
router = DefaultRouter()

# Add viewsets to router when created
# router.register('projects', ProjectViewSet)

urlpatterns = [
    # Add URL patterns here
] + router.urls