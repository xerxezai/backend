from django.contrib import admin

from .models import Invoice, InvoiceItem, Payment, RecurringInvoice, CreditNote


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


@admin.register(RecurringInvoice)
class RecurringInvoiceAdmin(admin.ModelAdmin):
    list_display = ('customer', 'amount', 'frequency', 'next_due_date', 'status', 'last_generated_at')
    list_filter = ('status', 'frequency')
    autocomplete_fields = ('customer',)


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ('number', 'invoice', 'customer', 'amount', 'date', 'status')
    list_filter = ('status',)
    search_fields = ('number', 'customer__name', 'invoice__number')
    autocomplete_fields = ('invoice', 'customer')
