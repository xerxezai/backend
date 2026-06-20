from django.contrib import admin

from .models import Invoice, InvoiceItem, Payment


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('number', 'customer', 'issue_date', 'due_date', 'status', 'total', 'amount_paid', 'balance')
    list_filter = ('status', 'issue_date')
    search_fields = ('number', 'customer__name')
    autocomplete_fields = ('customer', 'sales_order')
    inlines = [InvoiceItemInline, PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'method', 'paid_at', 'reference')
    list_filter = ('method', 'paid_at')
    autocomplete_fields = ('invoice',)
