from django.contrib import admin

from .models import Project, Milestone, Task, BudgetEntry


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('project_code', 'name', 'client', 'status', 'priority', 'manager', 'progress')
    list_filter = ('status', 'priority')
    search_fields = ('project_code', 'name', 'client')
    autocomplete_fields = ('manager',)


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ('project', 'title', 'due_date', 'status')
    list_filter = ('status',)
    search_fields = ('title', 'project__name', 'project__project_code')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('project', 'title', 'status', 'priority', 'assigned_to', 'due_date')
    list_filter = ('status', 'priority')
    search_fields = ('title', 'project__name')


@admin.register(BudgetEntry)
class BudgetEntryAdmin(admin.ModelAdmin):
    list_display = ('project', 'category', 'description', 'budgeted_amount', 'actual_amount', 'date')
    list_filter = ('category',)
    search_fields = ('description', 'project__name')
