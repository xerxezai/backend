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
    search_fields = ('code', 'name', 'barcode')
    autocomplete_fields = ('category',)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'location', 'is_active')
    search_fields = ('code', 'name', 'location')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('occurred_at', 'type', 'product', 'warehouse', 'quantity', 'reason', 'created_by', 'reference')
    list_filter = ('type', 'warehouse')
    search_fields = ('product__name', 'product__code', 'reference', 'reason')
    autocomplete_fields = ('product', 'warehouse')
    # created_by is never manually editable here — it's always the admin user who
    # created/last touched the row, closing the gap that let movements created via the
    # admin (bypassing the API's perform_create) end up with no recorded user.
    readonly_fields = ('created_by',)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
