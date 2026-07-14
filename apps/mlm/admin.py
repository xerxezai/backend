from django.contrib import admin
from .models import Distributor, Commission, Payout, MLMSettings


@admin.register(Distributor)
class DistributorAdmin(admin.ModelAdmin):
    list_display = ('distributor_id', 'name', 'sponsor', 'level', 'status', 'joining_date', 'total_sales', 'total_earnings')
    list_filter = ('status', 'level')
    search_fields = ('distributor_id', 'name', 'email')


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ('distributor', 'order', 'level', 'rate', 'amount', 'status', 'created_date')
    list_filter = ('status', 'level')
    search_fields = ('distributor__name', 'distributor__distributor_id', 'order__number')


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ('distributor', 'amount', 'payout_date', 'method', 'reference_number', 'status')
    list_filter = ('status', 'method')
    search_fields = ('distributor__name', 'reference_number')


@admin.register(MLMSettings)
class MLMSettingsAdmin(admin.ModelAdmin):
    list_display = ('level1_rate', 'level2_rate', 'level3_rate')
