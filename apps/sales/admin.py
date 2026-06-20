from django.contrib import admin

from .models import Quotation, QuotationItem, SalesOrder


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('number', 'customer', 'issue_date', 'valid_until', 'status', 'total')
    list_filter = ('status', 'issue_date')
    search_fields = ('number', 'customer__name')
    autocomplete_fields = ('customer',)
    inlines = [QuotationItemInline]


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'customer', 'order_date', 'status', 'total')
    list_filter = ('status',)
    search_fields = ('number', 'customer__name')
    autocomplete_fields = ('customer', 'quotation')
