"""
MLM Admin configuration for XERXEZ Backend
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import MLMProfile, CommissionStructure, Transaction, Commission, Earning


@admin.register(MLMProfile)
class MLMProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'referral_code', 'referrer',
        'level', 'total_referrals', 'is_active', 'joined_at',
    ]
    list_filter = ['is_active', 'level']
    search_fields = ['user__username', 'user__email', 'referral_code']
    readonly_fields = ['referral_code', 'joined_at', 'level']
    raw_id_fields = ['user', 'referrer']
    ordering = ['-joined_at']

    fieldsets = (
        ('User', {'fields': ('user', 'referral_code', 'is_active')}),
        ('Referral Info', {'fields': ('referrer', 'level', 'total_referrals', 'joined_at')}),
    )


@admin.register(CommissionStructure)
class CommissionStructureAdmin(admin.ModelAdmin):
    list_display = ['level', 'commission_rate_display', 'is_active', 'description', 'updated_at']
    list_filter = ['is_active']
    ordering = ['level']

    def commission_rate_display(self, obj):
        return f"{obj.commission_rate}%"
    commission_rate_display.short_description = 'Rate'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'status', 'reference', 'created_at']
    list_filter = ['status']
    search_fields = ['user__username', 'reference', 'description']
    readonly_fields = ['reference', 'created_at', 'updated_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = [
        'earner', 'source_user', 'level',
        'commission_rate_display', 'amount', 'status', 'created_at',
    ]
    list_filter = ['status', 'level']
    search_fields = ['earner__username', 'source_user__username', 'transaction__reference']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    def commission_rate_display(self, obj):
        return f"{obj.commission_rate}%"
    commission_rate_display.short_description = 'Rate'


@admin.register(Earning)
class EarningAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'total_earned', 'pending_earnings',
        'approved_earnings', 'paid_earnings',
        'last_payout', 'updated_at',
    ]
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['updated_at']
    ordering = ['-total_earned']

    actions = ['recalculate_earnings']

    def recalculate_earnings(self, request, queryset):
        for earning in queryset:
            earning.recalculate()
        self.message_user(request, f"Recalculated earnings for {queryset.count()} users.")
    recalculate_earnings.short_description = 'Recalculate selected earnings'
