"""
URL configuration for Analytics app
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

app_name = 'analytics'
router = DefaultRouter()

# Add viewsets to router when created
# router.register('events', AnalyticsEventViewSet)

urlpatterns = [
    # Add URL patterns here
] + router.urls