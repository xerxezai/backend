"""
URL configuration for Users app
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

app_name = 'users'
router = DefaultRouter()

# Add viewsets to router when created
# router.register('profiles', ProfileViewSet)

urlpatterns = [
    # Add URL patterns here
] + router.urls