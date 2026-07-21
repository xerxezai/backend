from django.contrib import admin

from .models import PartnerApplication


@admin.register(PartnerApplication)
class PartnerApplicationAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'country', 'status', 'estimated_deals', 'created_at')
    list_filter = ('status', 'country')
    search_fields = ('full_name', 'email', 'city')
