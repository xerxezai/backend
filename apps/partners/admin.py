from django.contrib import admin

from .models import PartnerApplication, PartnerLead


@admin.register(PartnerApplication)
class PartnerApplicationAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'country', 'status', 'estimated_deals', 'created_at')
    list_filter = ('status', 'country')
    search_fields = ('full_name', 'email', 'city')


@admin.register(PartnerLead)
class PartnerLeadAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'partner', 'package', 'deal_value', 'status', 'created_at')
    list_filter = ('status', 'package')
    search_fields = ('client_name', 'company', 'partner__full_name')
