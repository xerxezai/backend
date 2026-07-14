from django.contrib import admin

from .models import Account, JournalEntry, JournalLine, Expense, TaxReport


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'type', 'parent', 'is_active')
    list_filter = ('type', 'is_active')
    search_fields = ('code', 'name')
    autocomplete_fields = ('parent',)


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 2
    autocomplete_fields = ('account',)


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('number', 'date', 'description', 'posted', 'is_balanced')
    list_filter = ('posted', 'date')
    search_fields = ('number', 'description', 'reference')
    inlines = [JournalLineInline]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_number', 'category', 'amount', 'date', 'paid_by', 'status')
    list_filter = ('status', 'category')
    search_fields = ('expense_number', 'category', 'description', 'paid_by')


@admin.register(TaxReport)
class TaxReportAdmin(admin.ModelAdmin):
    list_display = ('period', 'total_revenue', 'total_tax_collected', 'total_tax_paid', 'net_tax')
    search_fields = ('period',)
