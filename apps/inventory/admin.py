from django.contrib import admin

from .models import Product, ProductCategory, StockMovement, Warehouse


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'parent')
    search_fields = ('code', 'name')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'unit', 'cost_price', 'sale_price', 'is_digital', 'is_active')
    list_filter = ('is_active', 'is_digital', 'category')
    search_fields = ('code', 'name')
    autocomplete_fields = ('category',)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'location', 'is_active')
    search_fields = ('code', 'name', 'location')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('occurred_at', 'type', 'product', 'warehouse', 'quantity', 'reference')
    list_filter = ('type', 'warehouse')
    search_fields = ('product__name', 'product__code', 'reference')
    autocomplete_fields = ('product', 'warehouse')
