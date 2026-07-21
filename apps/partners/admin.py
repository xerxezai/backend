from django.contrib import admin

from .models import Partner, PartnerDeal


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'partner_code', 'country', 'status', 'commission_tier', 'total_deals', 'joined_at')
    list_filter = ('status', 'commission_tier', 'country')
    search_fields = ('full_name', 'email', 'partner_code', 'city')


@admin.register(PartnerDeal)
class PartnerDealAdmin(admin.ModelAdmin):
    list_display = ('deal_number', 'client_company', 'partner', 'package', 'status', 'deal_value', 'commission_status', 'submitted_at')
    list_filter = ('status', 'package', 'commission_status')
    search_fields = ('deal_number', 'client_company', 'partner__full_name')
