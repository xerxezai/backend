from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'username', 'ip_address', 'source', 'created_at')
    list_filter = ('action', 'source', 'created_at')
    search_fields = ('username', 'ip_address')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False  # audit rows are system-written only

    def has_change_permission(self, request, obj=None):
        return False  # read-only trail — never editable
