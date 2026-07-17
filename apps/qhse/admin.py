from django.contrib import admin

from .models import Incident, Inspection, RiskRegister, SafetyChecklist, ChecklistItem, ComplianceRecord


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('incident_number', 'title', 'incident_type', 'severity', 'status', 'date')
    list_filter = ('incident_type', 'severity', 'status')
    search_fields = ('incident_number', 'title', 'location')


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'inspection_type', 'status', 'scheduled_date', 'score')
    list_filter = ('inspection_type', 'status')
    search_fields = ('title', 'location')


@admin.register(RiskRegister)
class RiskRegisterAdmin(admin.ModelAdmin):
    list_display = ('risk_id', 'title', 'category', 'risk_score', 'risk_level', 'status')
    list_filter = ('category', 'risk_level', 'status')
    search_fields = ('risk_id', 'title')


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 1


@admin.register(SafetyChecklist)
class SafetyChecklistAdmin(admin.ModelAdmin):
    list_display = ('title', 'checklist_type', 'date', 'status', 'created_by')
    list_filter = ('checklist_type', 'status')
    search_fields = ('title', 'location')
    inlines = [ChecklistItemInline]


@admin.register(ComplianceRecord)
class ComplianceRecordAdmin(admin.ModelAdmin):
    list_display = ('title', 'compliance_type', 'due_date', 'status', 'responsible_person')
    list_filter = ('compliance_type', 'status')
    search_fields = ('title',)
