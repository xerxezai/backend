from django.contrib import admin

from .models import Asset, MaintenanceRecord, AssetDepreciation


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('asset_code', 'name', 'category', 'status', 'location', 'assigned_to', 'purchase_cost')
    list_filter = ('category', 'status')
    search_fields = ('asset_code', 'name', 'location')
    autocomplete_fields = ('assigned_to',)


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ('asset', 'maintenance_type', 'date', 'cost', 'performed_by')
    list_filter = ('maintenance_type',)
    search_fields = ('asset__name', 'asset__asset_code', 'performed_by')


@admin.register(AssetDepreciation)
class AssetDepreciationAdmin(admin.ModelAdmin):
    list_display = ('asset', 'year', 'opening_value', 'depreciation_amount', 'closing_value')
    list_filter = ('year',)
