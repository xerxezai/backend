from django.contrib import admin
from django.utils.html import format_html

from .models import Document, DocumentVersion


class DocumentVersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    readonly_fields = ('version_number', 'file', 'uploaded_by', 'notes', 'created_at')
    can_delete = False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'category_badge', 'version', 'status_badge', 'uploaded_by', 'approved_by', 'created_at')
    list_filter = ('category', 'status', 'created_at')
    search_fields = ('title', 'description', 'uploaded_by__username', 'approved_by__username')
    ordering = ('-created_at',)
    list_per_page = 30
    date_hierarchy = 'created_at'
    inlines = [DocumentVersionInline]
    actions = ['mark_approved', 'mark_rejected']

    fieldsets = (
        ('Document', {
            'fields': ('title', 'description', 'category', 'file', 'version'),
        }),
        ('Workflow', {
            'fields': ('status', 'uploaded_by', 'approved_by'),
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    readonly_fields = ('uploaded_by', 'approved_by', 'created_at', 'updated_at')

    CATEGORY_COLORS = {
        'engineering_drawing': ('#e3f2fd', '#1565c0'),
        'contract':            ('#ede7f6', '#5e35b1'),
        'invoice':             ('#e8f5e9', '#2e7d32'),
        'hr_document':         ('#fff3e0', '#e65100'),
        'safety_qhse':         ('#ffebee', '#c62828'),
        'procurement':         ('#e0f2f1', '#00695c'),
        'project_report':      ('#f3e5f5', '#8e24aa'),
        'other':               ('#f5f5f5', '#555'),
    }

    @admin.display(description='Category')
    def category_badge(self, obj):
        bg, fg = self.CATEGORY_COLORS.get(obj.category, ('#f5f5f5', '#555'))
        return format_html(
            '<span style="background:{};color:{};border-radius:100px;padding:2px 10px;'
            'font-size:11px;font-weight:700">{}</span>',
            bg, fg, obj.get_category_display()
        )

    STATUS_COLORS = {
        'draft':        ('#f1f5f9', '#64748b'),
        'under_review': ('#fff3e0', '#e65100'),
        'approved':     ('#e8f5e9', '#2e7d32'),
        'rejected':     ('#ffebee', '#c62828'),
    }

    @admin.display(description='Status')
    def status_badge(self, obj):
        bg, fg = self.STATUS_COLORS.get(obj.status, ('#f5f5f5', '#555'))
        return format_html(
            '<span style="background:{};color:{};border-radius:100px;padding:2px 10px;'
            'font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em">{}</span>',
            bg, fg, obj.get_status_display()
        )

    @admin.action(description='Mark selected as Approved')
    def mark_approved(self, request, queryset):
        updated = queryset.update(status='approved', approved_by=request.user)
        self.message_user(request, f'{updated} document(s) marked as approved.')

    @admin.action(description='Mark selected as Rejected')
    def mark_rejected(self, request, queryset):
        updated = queryset.update(status='rejected', approved_by=request.user)
        self.message_user(request, f'{updated} document(s) marked as rejected.')


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ('document', 'version_number', 'uploaded_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('document__title', 'version_number', 'notes')
    ordering = ('-created_at',)
    readonly_fields = ('document', 'version_number', 'file', 'uploaded_by', 'notes', 'created_at')
