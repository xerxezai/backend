from django.contrib import admin
from .models import Supplier, PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem, Bill


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0


class GoodsReceiptItemInline(admin.TabularInline):
    model = GoodsReceiptItem
    extra = 0


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'city', 'country', 'payment_terms', 'rating', 'is_active')
    search_fields = ('name', 'email', 'city', 'country')
    list_filter = ('is_active', 'country')


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'supplier', 'order_date', 'expected_delivery', 'status', 'total')
    list_filter = ('status',)
    search_fields = ('po_number', 'supplier__name')
    inlines = [PurchaseOrderItemInline]


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'purchase_order', 'received_date', 'received_by')
    search_fields = ('receipt_number', 'purchase_order__po_number')
    inlines = [GoodsReceiptItemInline]


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('bill_number', 'supplier', 'purchase_order', 'issue_date', 'due_date', 'amount', 'status')
    list_filter = ('status',)
    search_fields = ('bill_number', 'supplier__name', 'purchase_order__po_number')
