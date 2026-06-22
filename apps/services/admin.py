from django.contrib import admin
from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_published', 'order', 'created_at']
    list_filter = ['is_published']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}