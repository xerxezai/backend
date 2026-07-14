from django.contrib import admin
from .models import Shipment, TrackingUpdate, Delivery, Warehouse


class TrackingUpdateInline(admin.TabularInline):
    model = TrackingUpdate
    extra = 0


class DeliveryInline(admin.TabularInline):
    model = Delivery
    extra = 0


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ('shipment_number', 'tracking_number', 'customer', 'carrier', 'status', 'estimated_delivery', 'actual_delivery', 'created_at')
    list_filter = ('status',)
    search_fields = ('shipment_number', 'tracking_number', 'customer__name', 'carrier')
    inlines = [TrackingUpdateInline, DeliveryInline]


@admin.register(TrackingUpdate)
class TrackingUpdateAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'status', 'location', 'occurred_at')
    list_filter = ('occurred_at',)
    search_fields = ('shipment__tracking_number', 'status', 'location')


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'delivery_date', 'delivered_by', 'status')
    list_filter = ('status',)
    search_fields = ('shipment__tracking_number', 'delivered_by')


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'capacity', 'manager', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'location')
