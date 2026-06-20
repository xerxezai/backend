from django.contrib import admin

from .models import Activity, Contact, Customer, Lead


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'company', 'email', 'phone', 'industry', 'is_active')
    search_fields = ('code', 'name', 'company', 'email')
    list_filter = ('is_active', 'industry')
    inlines = [ContactInline]


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'status', 'source', 'estimated_value', 'assigned_to', 'created_at')
    list_filter = ('status', 'source', 'assigned_to')
    search_fields = ('name', 'company', 'email')
    autocomplete_fields = ('customer', 'assigned_to')


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('occurred_at', 'type', 'summary', 'user', 'lead', 'customer')
    list_filter = ('type', 'occurred_at')
    search_fields = ('summary', 'body')
    autocomplete_fields = ('user', 'lead', 'customer')


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'customer', 'role', 'email', 'phone', 'is_primary')
    search_fields = ('name', 'email', 'customer__name')
    autocomplete_fields = ('customer',)
