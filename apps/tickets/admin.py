from django.contrib import admin

from .models import Ticket, TicketCategory, TicketComment


@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('number', 'subject', 'customer', 'category', 'priority', 'status', 'assignee', 'created_at')
    list_filter = ('status', 'priority', 'category')
    search_fields = ('number', 'subject', 'customer__name', 'requester_email')
    autocomplete_fields = ('customer', 'category', 'assignee')
    inlines = [TicketCommentInline]
