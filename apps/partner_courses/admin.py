from django.contrib import admin
from .models import PartnerCourse


@admin.register(PartnerCourse)
class PartnerCourseAdmin(admin.ModelAdmin):
    list_display = ['partner_name', 'title', 'category', 'level', 'is_active', 'is_featured', 'order', 'created_at']
    list_filter = ['is_active', 'is_featured', 'category', 'level']
    search_fields = ['partner_name', 'title']
