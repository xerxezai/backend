from django.contrib import admin

from .models import Company, CompanyUser


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'status', 'plan', 'country', 'created_at')
    list_filter = ('status', 'plan', 'country')
    search_fields = ('name', 'slug', 'email')


@admin.register(CompanyUser)
class CompanyUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'role', 'is_active', 'joined_at')
    list_filter = ('role', 'is_active', 'company')
    search_fields = ('user__username', 'user__email', 'company__name')
    autocomplete_fields = ('user', 'company')
