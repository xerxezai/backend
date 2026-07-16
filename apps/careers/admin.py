from django.contrib import admin
from django.utils.html import format_html

from .models import CareerApplication


@admin.register(CareerApplication)
class CareerApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'email_link', 'position', 'experience', 'status_badge',
                     'resume_link', 'applied_at')
    list_filter = ('status', 'position', 'applied_at')
    search_fields = ('name', 'email', 'phone', 'position', 'cover_letter')
    readonly_fields = ('name', 'email', 'phone', 'position', 'experience', 'linkedin',
                        'portfolio', 'cover_letter', 'resume_file', 'applied_at')
    ordering = ('-applied_at',)
    list_per_page = 30
    date_hierarchy = 'applied_at'
    actions = ['mark_reviewing', 'mark_shortlisted', 'mark_rejected']

    fieldsets = (
        ('Applicant', {
            'fields': ('name', 'email', 'phone', 'linkedin', 'portfolio'),
        }),
        ('Application', {
            'fields': ('position', 'experience', 'cover_letter', 'resume_file'),
        }),
        ('Status', {
            'fields': ('status', 'applied_at'),
        }),
    )

    @admin.display(description='Email')
    def email_link(self, obj):
        return format_html('<a href="mailto:{}">{}</a>', obj.email, obj.email)

    @admin.display(description='Resume')
    def resume_link(self, obj):
        if not obj.resume_file:
            return '—'
        return format_html('<a href="{}" target="_blank">Download</a>', obj.resume_file.url)

    STATUS_COLORS = {
        'new':         ('#e3f2fd', '#1565c0'),
        'reviewing':   ('#fff3e0', '#e65100'),
        'shortlisted': ('#e8f5e9', '#2e7d32'),
        'rejected':    ('#ffebee', '#c62828'),
    }

    @admin.display(description='Status')
    def status_badge(self, obj):
        bg, fg = self.STATUS_COLORS.get(obj.status, ('#f5f5f5', '#555'))
        return format_html(
            '<span style="background:{};color:{};border-radius:100px;padding:2px 10px;'
            'font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em">{}</span>',
            bg, fg, obj.get_status_display()
        )

    @admin.action(description='Mark selected as Reviewing')
    def mark_reviewing(self, request, queryset):
        updated = queryset.update(status='reviewing')
        self.message_user(request, f'{updated} application(s) marked as reviewing.')

    @admin.action(description='Mark selected as Shortlisted')
    def mark_shortlisted(self, request, queryset):
        updated = queryset.update(status='shortlisted')
        self.message_user(request, f'{updated} application(s) marked as shortlisted.')

    @admin.action(description='Mark selected as Rejected')
    def mark_rejected(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f'{updated} application(s) marked as rejected.')
