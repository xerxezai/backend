from django.contrib import admin

from .models import Attendance, Department, Employee, LeaveRequest


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'manager', 'parent')
    search_fields = ('code', 'name')
    autocomplete_fields = ('manager', 'parent')


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('code', 'full_name', 'department', 'designation', 'status', 'joined_on')
    list_filter = ('status', 'department')
    search_fields = ('code', 'full_name', 'email')
    autocomplete_fields = ('user', 'department')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'check_in', 'check_out', 'hours')
    list_filter = ('date',)
    autocomplete_fields = ('employee',)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'type', 'from_date', 'to_date', 'days', 'status')
    list_filter = ('status', 'type')
    autocomplete_fields = ('employee', 'decided_by')
