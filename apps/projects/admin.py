from django.contrib import admin

from .models import Project, Task, TimeEntry


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ('title', 'assignee', 'status', 'priority', 'due_date')
    show_change_link = True


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'customer', 'manager', 'status', 'start_date', 'end_date', 'budget')
    list_filter = ('status',)
    search_fields = ('code', 'name', 'customer__name')
    autocomplete_fields = ('customer', 'manager')
    inlines = [TaskInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'assignee', 'status', 'priority', 'due_date')
    list_filter = ('status', 'priority')
    search_fields = ('title', 'project__name')
    autocomplete_fields = ('project', 'assignee')


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'task', 'hours')
    list_filter = ('date', 'user')
    autocomplete_fields = ('task', 'user')
