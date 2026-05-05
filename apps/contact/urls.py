"""
URL configuration for Contact app
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

app_name = 'contact'
router = DefaultRouter()

# Add viewsets to router when created
# router.register('messages', ContactMessageViewSet)

urlpatterns = [
    # Add URL patterns here
] + router.urls