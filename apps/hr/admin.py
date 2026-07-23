from django.contrib import admin

from .models import (Attendance, Department, Employee, LeaveRequest, LeavePolicy, PaySlip,
                     Payroll, SalaryStructure, Shift, Holiday, Overtime)


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
    list_display = ('employee', 'date', 'check_in', 'check_out', 'hours', 'status')
    list_filter = ('date', 'status')
    autocomplete_fields = ('employee',)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'type', 'from_date', 'to_date', 'days', 'status', 'decided_by')
    list_filter = ('status', 'type')
    autocomplete_fields = ('employee', 'decided_by')


@admin.register(LeavePolicy)
class LeavePolicyAdmin(admin.ModelAdmin):
    list_display = ('company', 'leave_type', 'days_allowed', 'carry_forward', 'max_carry_forward_days', 'is_active')
    list_filter = ('leave_type', 'is_active', 'carry_forward')
    autocomplete_fields = ('company',)


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'end_time')
    search_fields = ('name',)
    filter_horizontal = ('employees',)


@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    list_display = ('employee', 'basic_salary', 'effective_date')
    search_fields = ('employee__full_name', 'employee__code')
    autocomplete_fields = ('employee',)


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ('employee', 'month', 'year', 'working_days', 'present_days', 'gross', 'net_salary', 'status', 'paid_at')
    list_filter = ('status', 'year', 'month')
    search_fields = ('employee__full_name', 'employee__code')
    autocomplete_fields = ('employee', 'generated_by')


@admin.register(PaySlip)
class PaySlipAdmin(admin.ModelAdmin):
    list_display = ('payroll', 'pdf_ref', 'generated_at')
    search_fields = ('payroll__employee__full_name',)


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'holiday_type')
    list_filter = ('holiday_type',)
    search_fields = ('name',)


@admin.register(Overtime)
class OvertimeAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'extra_hours', 'rate', 'status', 'approved_by')
    list_filter = ('status', 'rate')
    search_fields = ('employee__full_name', 'employee__code')
    autocomplete_fields = ('employee', 'approved_by')
