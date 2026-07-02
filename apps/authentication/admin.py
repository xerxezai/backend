from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import OTPToken


@admin.register(OTPToken)
class OTPTokenAdmin(admin.ModelAdmin):
    list_display  = ('email', 'otp_display', 'status_badge', 'created_at', 'expires_at', 'has_reset_token')
    list_filter   = ('is_used',)
    search_fields = ('email',)
    ordering      = ('-created_at',)
    readonly_fields = ('email', 'otp', 'reset_token', 'created_at', 'expires_at', 'is_used')
    date_hierarchy = 'created_at'

    def otp_display(self, obj):
        return obj.otp if obj.otp else '—'
    otp_display.short_description = 'OTP'

    def status_badge(self, obj):
        now = timezone.now()
        if obj.is_used and obj.reset_token:
            color, label = '#C9883A', 'OTP Verified'
        elif obj.is_used:
            color, label = '#6B6B6B', 'Used'
        elif now > obj.expires_at:
            color, label = '#ef4444', 'Expired'
        else:
            remaining = int((obj.expires_at - now).total_seconds() // 60)
            color, label = '#10b981', f'Active ({remaining}m left)'
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600">{}</span>',
            color, label,
        )
    status_badge.short_description = 'Status'

    def has_reset_token(self, obj):
        return bool(obj.reset_token)
    has_reset_token.boolean = True
    has_reset_token.short_description = 'Reset token issued'

    def has_add_permission(self, request):
        return False  # OTP tokens are created by the API only
