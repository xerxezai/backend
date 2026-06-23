from django.contrib import admin
from .models import Vendor, PurchaseOrder, PurchaseOrderItem


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'email', 'phone', 'contact_person', 'is_active')
    search_fields = ('code', 'name', 'email')
    list_filter = ('is_active',)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'vendor', 'order_date', 'status', 'total')
    list_filter = ('status',)
    search_fields = ('number', 'vendor__name')
    inlines = [PurchaseOrderItemInline]


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'description', 'quantity', 'unit_price', 'line_total')
