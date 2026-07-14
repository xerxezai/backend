from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DistributorViewSet, CommissionViewSet, PayoutViewSet, MLMDashboardView, MLMSettingsView,
)

app_name = 'mlm'
router = DefaultRouter()
router.register('distributors', DistributorViewSet, basename='distributor')
router.register('commissions', CommissionViewSet, basename='commission')
router.register('payouts', PayoutViewSet, basename='payout')

urlpatterns = [
    path('dashboard/', MLMDashboardView.as_view(), name='mlm-dashboard'),
    path('settings/', MLMSettingsView.as_view(), name='mlm-settings'),
] + router.urls
