from rest_framework.routers import DefaultRouter
from .views import ShipmentViewSet, TrackingUpdateViewSet

app_name = 'logistics'
router = DefaultRouter()
router.register('shipments', ShipmentViewSet, basename='shipment')
router.register('tracking', TrackingUpdateViewSet, basename='tracking-update')

urlpatterns = router.urls
