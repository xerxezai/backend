from rest_framework.routers import DefaultRouter
from .views import ProductCategoryViewSet, ProductViewSet, WarehouseViewSet, StockMovementViewSet

app_name = 'inventory'
router = DefaultRouter()
router.register('categories', ProductCategoryViewSet, basename='product-category')
router.register('products', ProductViewSet, basename='product')
router.register('warehouses', WarehouseViewSet, basename='warehouse')
router.register('stock-movements', StockMovementViewSet, basename='stock-movement')

urlpatterns = router.urls
