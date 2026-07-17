from django.contrib import admin

from .models import Module, UserModuleAccess, AccessRequest


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'display_name')


@admin.register(UserModuleAccess)
class UserModuleAccessAdmin(admin.ModelAdmin):
    list_display = ('user', 'module', 'role', 'is_active', 'granted_by', 'granted_at')
    list_filter = ('role', 'is_active', 'module')
    search_fields = ('user__username', 'user__email')
    autocomplete_fields = ('user', 'module', 'granted_by')


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'module', 'status', 'reviewed_by', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__username',)
