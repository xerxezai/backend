from datetime import datetime, date, timedelta
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import (
    Department, Employee, Attendance, LeaveRequest, LeavePolicy, Shift, SalaryStructure, Payroll, PaySlip,
    PerformanceReview, EmployeeDocument, OnboardingChecklist, ExitManagement, ExitInterview, ExitChecklistItem,
    Holiday, Overtime,
)


def _gen_code(model, prefix, pad=3):
    n = model.objects.count()
    while True:
        code = f"{prefix}{str(n + 1).zfill(pad)}"
        if not model.objects.filter(code=code).exists():
            return code
        n += 1


class DepartmentSerializer(serializers.ModelSerializer):
    # Explicitly declared (for allow_blank, since it's auto-generated when omitted) — but that
    # means ModelSerializer's automatic UniqueValidator is NOT applied for a manually-declared
    # field, so it has to be added back here, or a collision only surfaces as an unhandled
    # IntegrityError at the database insert instead of a clean 400.
    code = serializers.CharField(required=False, allow_blank=True, validators=[UniqueValidator(queryset=Department.objects.all())])
    manager_username = serializers.CharField(source='manager.username', read_only=True, default=None)
    head_name = serializers.CharField(source='head.full_name', read_only=True, default=None)
    head_code = serializers.CharField(source='head.code', read_only=True, default=None)
    employee_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Department
        fields = '__all__'

    def create(self, validated_data):
        if not validated_data.get('code'):
            validated_data['code'] = _gen_code(Department, 'DEPT')
        return super().create(validated_data)


class EmployeeSerializer(serializers.ModelSerializer):
    # Same reasoning as DepartmentSerializer.code above — this manually-declared field needs
    # its UniqueValidator added back explicitly, otherwise a code collision (e.g. two near-
    # simultaneous creates racing _gen_code(), or a client submitting an explicit duplicate
    # code) is an unhandled IntegrityError -> 500 instead of a clean 400.
    code = serializers.CharField(required=False, allow_blank=True, validators=[UniqueValidator(queryset=Employee.objects.all())])
    department_name = serializers.CharField(source='department.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Employee
        fields = '__all__'
        read_only_fields = ['created_by']

    def create(self, validated_data):
        if not validated_data.get('code'):
            validated_data['code'] = _gen_code(Employee, 'EMP')
        return super().create(validated_data)


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True, default=None)

    class Meta:
        model = Attendance
        fields = '__all__'

    def validate(self, attrs):
        # hours is always derived from check_in/check_out — for self-service clock-out
        # (see AttendanceViewSet.clock_out) and for manual admin entries alike, so "Clock Out
        # minus Clock In" is the one source of truth regardless of how the record was made.
        check_in = attrs.get('check_in', getattr(self.instance, 'check_in', None))
        check_out = attrs.get('check_out', getattr(self.instance, 'check_out', None))
        if check_in and check_out:
            delta = check_out - check_in
            attrs['hours'] = round(max(delta.total_seconds(), 0) / 3600, 2)
        return attrs


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.code', read_only=True)
    decided_by_username = serializers.CharField(source='decided_by.username', read_only=True, default=None)
    decided_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = '__all__'
        read_only_fields = ['days', 'status', 'decided_by', 'decided_at', 'rejection_reason']

    def get_decided_by_name(self, obj):
        if not obj.decided_by_id:
            return None
        return obj.decided_by.get_full_name() or obj.decided_by.username

    def validate(self, attrs):
        from_date = attrs.get('from_date') or getattr(self.instance, 'from_date', None)
        to_date = attrs.get('to_date') or getattr(self.instance, 'to_date', None)
        if from_date and to_date:
            if to_date < from_date:
                raise serializers.ValidationError({'to_date': 'To date must be on or after the from date.'})
            attrs['days'] = (to_date - from_date).days + 1
        return attrs


class LeavePolicySerializer(serializers.ModelSerializer):
    leave_type_display = serializers.CharField(source='get_leave_type_display', read_only=True)

    class Meta:
        model = LeavePolicy
        fields = '__all__'
        read_only_fields = ['company']


class ShiftSerializer(serializers.ModelSerializer):
    employee_ids = serializers.PrimaryKeyRelatedField(
        source='employees', queryset=Employee.objects.all(), many=True, required=False,
    )
    employee_names = serializers.SerializerMethodField()
    employee_count = serializers.SerializerMethodField()
    employees_detail = serializers.SerializerMethodField()
    total_hours = serializers.SerializerMethodField()

    class Meta:
        model = Shift
        fields = [
            'id', 'name', 'shift_type', 'start_time', 'end_time', 'break_duration', 'grace_period',
            'working_days', 'color', 'is_active', 'created_at',
            'employee_ids', 'employee_names', 'employee_count', 'employees_detail', 'total_hours',
        ]

    def get_employee_names(self, obj):
        return [e.full_name for e in obj.employees.all()]

    def get_employee_count(self, obj):
        return obj.employees.count()

    def get_employees_detail(self, obj):
        return [{'id': e.id, 'full_name': e.full_name, 'code': e.code} for e in obj.employees.all()]

    def get_total_hours(self, obj):
        if not obj.start_time or not obj.end_time:
            return 0
        start = datetime.combine(date.min, obj.start_time)
        end = datetime.combine(date.min, obj.end_time)
        if end <= start:
            end += timedelta(days=1)
        minutes = (end - start).total_seconds() / 60 - (obj.break_duration or 0)
        return round(max(minutes, 0) / 60, 2)


class SalaryStructureSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.code', read_only=True)

    class Meta:
        model = SalaryStructure
        fields = '__all__'


class PayrollSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.code', read_only=True)
    employee_designation = serializers.CharField(source='employee.designation', read_only=True, default='')
    department_name = serializers.CharField(source='employee.department.name', read_only=True, default=None)
    company_name = serializers.CharField(source='employee.company.name', read_only=True, default=None)
    generated_by_username = serializers.CharField(source='generated_by.username', read_only=True)
    has_payslip = serializers.SerializerMethodField()

    class Meta:
        model = Payroll
        fields = '__all__'

    def get_has_payslip(self, obj):
        return hasattr(obj, 'payslip')


class PaySlipSerializer(serializers.ModelSerializer):
    payroll_detail = PayrollSerializer(source='payroll', read_only=True)

    class Meta:
        model = PaySlip
        fields = '__all__'


class PerformanceReviewSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    reviewer_username = serializers.CharField(source='reviewer.username', read_only=True)
    rating_label = serializers.CharField(source='get_rating_display', read_only=True)

    class Meta:
        model = PerformanceReview
        fields = '__all__'
        read_only_fields = ['reviewer', 'review_date']


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.code', read_only=True)
    doc_type_label = serializers.CharField(source='get_doc_type_display', read_only=True)
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True, default=None)
    verified_by_username = serializers.CharField(source='verified_by.username', read_only=True, default=None)
    file_url = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    expiry_status = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeDocument
        fields = '__all__'
        read_only_fields = ['employee', 'uploaded_at', 'uploaded_by', 'expiry_notified', 'verified_by', 'verified_at', 'is_verified']

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def get_days_until_expiry(self, obj):
        if not obj.expiry_date:
            return None
        return (obj.expiry_date - date.today()).days

    def get_is_expired(self, obj):
        return bool(obj.expiry_date and obj.expiry_date < date.today())

    def get_expiry_status(self, obj):
        if not obj.expiry_date:
            return 'valid'
        days = (obj.expiry_date - date.today()).days
        if days < 0:
            return 'expired'
        if days <= 30:
            return 'expiring_soon'
        return 'valid'


class OnboardingChecklistSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.code', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True, default=None)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True, default=None)
    category_label = serializers.CharField(source='get_category_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = OnboardingChecklist
        fields = '__all__'
        read_only_fields = ['employee', 'completed', 'completed_at', 'reminder_sent']

    def get_is_overdue(self, obj):
        return bool(obj.due_date and obj.due_date < date.today() and obj.status != 'completed')


class ExitManagementSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.code', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True, default=None)
    reason_label = serializers.CharField(source='get_reason_display', read_only=True)
    settlement_payment_mode_label = serializers.CharField(source='get_settlement_payment_mode_display', read_only=True, default='')
    notice_days_remaining = serializers.SerializerMethodField()
    notice_period_progress_pct = serializers.SerializerMethodField()
    overall_status = serializers.SerializerMethodField()
    has_interview = serializers.SerializerMethodField()

    class Meta:
        model = ExitManagement
        fields = '__all__'
        read_only_fields = [
            'notice_period_start_date', 'pending_leaves', 'leave_encashment_amount',
            'gratuity_amount', 'pending_salary_days', 'pending_salary_amount', 'deductions_amount',
            'final_settlement_amount', 'settlement_paid', 'settlement_paid_date',
            'settlement_payment_mode', 'settlement_reference_number', 'exit_interview_done',
            'notice_reminder_sent', 'completed_at',
        ]

    def get_notice_days_remaining(self, obj):
        return (obj.last_working_day - date.today()).days

    def get_notice_period_progress_pct(self, obj):
        if not obj.notice_period_start_date or obj.last_working_day <= obj.notice_period_start_date:
            return 100
        total = (obj.last_working_day - obj.notice_period_start_date).days
        elapsed = (date.today() - obj.notice_period_start_date).days
        return max(0, min(100, round((elapsed / total) * 100)))

    def get_overall_status(self, obj):
        if obj.completed_at:
            return 'completed'
        if obj.last_working_day >= date.today():
            return 'notice_period'
        return 'clearance_pending'

    def get_has_interview(self, obj):
        return hasattr(obj, 'interview')


class ExitInterviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExitInterview
        fields = '__all__'
        read_only_fields = ['exit']


class ExitChecklistItemSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='exit.employee.full_name', read_only=True)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True, default=None)
    category_label = serializers.CharField(source='get_category_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = ExitChecklistItem
        fields = '__all__'
        read_only_fields = ['exit', 'completed', 'completed_at']

    def get_is_overdue(self, obj):
        return bool(obj.due_date and obj.due_date < date.today() and obj.status != 'completed')


class HolidaySerializer(serializers.ModelSerializer):
    next_occurrence = serializers.SerializerMethodField()
    days_until = serializers.SerializerMethodField()
    day_name = serializers.SerializerMethodField()

    class Meta:
        model = Holiday
        fields = '__all__'

    def get_next_occurrence(self, obj):
        return obj.next_occurrence()

    def get_days_until(self, obj):
        return (obj.next_occurrence() - date.today()).days

    def get_day_name(self, obj):
        return obj.next_occurrence().strftime('%A')


class OvertimeSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.code', read_only=True)
    approved_by_username = serializers.CharField(source='approved_by.username', read_only=True, default=None)

    class Meta:
        model = Overtime
        fields = '__all__'
        read_only_fields = ['status', 'approved_by', 'approved_at', 'rejection_reason']
