from django.contrib import admin
from .models import Affiliate, AffiliateClick, AffiliateCommission


@admin.register(Affiliate)
class AffiliateAdmin(admin.ModelAdmin):
    list_display = ['affiliate_code', 'full_name', 'email', 'status', 'commission_rate', 'total_clicks', 'total_conversions', 'total_earnings', 'created_at']
    list_filter = ['status']
    search_fields = ['affiliate_code', 'full_name', 'email']


@admin.register(AffiliateClick)
class AffiliateClickAdmin(admin.ModelAdmin):
    list_display = ['affiliate', 'course', 'clicked_at', 'converted']
    list_filter = ['converted']


@admin.register(AffiliateCommission)
class AffiliateCommissionAdmin(admin.ModelAdmin):
    list_display = ['affiliate', 'course', 'commission_amount', 'status', 'created_at']
    list_filter = ['status']
