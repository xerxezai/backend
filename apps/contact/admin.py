from django.contrib import admin
from django.utils.html import format_html
from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display  = ('full_name', 'email_link', 'phone', 'company', 'service_badge',
                     'urgency_badge', 'subject', 'is_read', 'created_at')
    list_filter   = ('urgency', 'is_read', 'service', 'created_at')
    search_fields = ('full_name', 'email', 'phone', 'company', 'subject', 'message')
    readonly_fields = ('full_name', 'email', 'phone', 'company',
                       'service', 'urgency', 'subject', 'message', 'created_at')
    ordering      = ('-created_at',)
    list_per_page = 30
    date_hierarchy = 'created_at'
    actions       = ['mark_as_read', 'mark_as_unread']

    fieldsets = (
        ('Contact Details', {
            'fields': ('full_name', 'email', 'phone', 'company'),
        }),
        ('Enquiry', {
            'fields': ('service', 'urgency', 'subject', 'message'),
        }),
        ('Meta', {
            'fields': ('is_read', 'created_at'),
        }),
    )

    @admin.display(description='Email')
    def email_link(self, obj):
        return format_html('<a href="mailto:{}">{}</a>', obj.email, obj.email)

    @admin.display(description='Service')
    def service_badge(self, obj):
        if not obj.service:
            return '—'
        return format_html(
            '<span style="background:#f0ede8;border-radius:100px;padding:2px 10px;'
            'font-size:11px;font-weight:600;color:#5a5650">{}</span>',
            obj.service
        )

    URGENCY_COLORS = {
        'normal':   ('#e8f5e9', '#2e7d32'),
        'urgent':   ('#fff3e0', '#e65100'),
        'critical': ('#ffebee', '#c62828'),
    }

    @admin.display(description='Urgency')
    def urgency_badge(self, obj):
        bg, fg = self.URGENCY_COLORS.get(obj.urgency, ('#f5f5f5', '#555'))
        return format_html(
            '<span style="background:{};color:{};border-radius:100px;padding:2px 10px;'
            'font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em">{}</span>',
            bg, fg, obj.get_urgency_display()
        )

    @admin.action(description='Mark selected messages as read')
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} message(s) marked as read.')

    @admin.action(description='Mark selected messages as unread')
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f'{updated} message(s) marked as unread.')
