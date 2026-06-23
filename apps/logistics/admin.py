from django.contrib import admin
from .models import Shipment, TrackingUpdate


class TrackingUpdateInline(admin.TabularInline):
    model = TrackingUpdate
    extra = 0


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ('tracking_number', 'customer', 'carrier', 'status', 'estimated_delivery', 'created_at')
    list_filter = ('status',)
    search_fields = ('tracking_number', 'customer__name', 'carrier')
    inlines = [TrackingUpdateInline]


@admin.register(TrackingUpdate)
class TrackingUpdateAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'status', 'location', 'occurred_at')
    list_filter = ('occurred_at',)
    search_fields = ('shipment__tracking_number', 'status', 'location')
