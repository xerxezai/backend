from django.contrib import admin

from .models import Account, JournalEntry, JournalLine


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
