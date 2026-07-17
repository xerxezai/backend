from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AssetViewSet, MaintenanceRecordViewSet, AssetDepreciationViewSet

router = DefaultRouter()
router.register('assets', AssetViewSet, basename='asset')
router.register('maintenance-records', MaintenanceRecordViewSet, basename='maintenancerecord')
router.register('depreciation', AssetDepreciationViewSet, basename='assetdepreciation')

urlpatterns = [
    path('', include(router.urls)),
]
