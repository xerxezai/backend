"""
URL configuration for Services app
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

app_name = 'services'
router = DefaultRouter()

# Add viewsets to router when created
# router.register('services', ServiceViewSet)

urlpatterns = [
    # Add URL patterns here
] + router.urls