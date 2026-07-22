from rest_framework import serializers
from .models import (
    Department, Employee, Attendance, LeaveRequest, Shift, SalaryStructure, Payroll, PaySlip,
    PerformanceReview, EmployeeDocument, OnboardingChecklist, ExitManagement,
)


def _gen_code(model, prefix, pad=3):
    n = model.objects.count()
    while True:
        code = f"{prefix}{str(n + 1).zfill(pad)}"
        if not model.objects.filter(code=code).exists():
            return code
        n += 1


class DepartmentSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, allow_blank=True)
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
    code = serializers.CharField(required=False, allow_blank=True)
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

    class Meta:
        model = Attendance
        fields = '__all__'


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    decided_by_username = serializers.CharField(source='decided_by.username', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = '__all__'


class ShiftSerializer(serializers.ModelSerializer):
    employee_ids = serializers.PrimaryKeyRelatedField(
        source='employees', queryset=Employee.objects.all(), many=True, required=False,
    )
    employee_names = serializers.SerializerMethodField()

    class Meta:
        model = Shift
        fields = ['id', 'name', 'start_time', 'end_time', 'employee_ids', 'employee_names']

    def get_employee_names(self, obj):
        return [e.full_name for e in obj.employees.all()]


class SalaryStructureSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.code', read_only=True)

    class Meta:
        model = SalaryStructure
        fields = '__all__'


class PayrollSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.code', read_only=True)
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
    doc_type_label = serializers.CharField(source='get_doc_type_display', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeDocument
        fields = '__all__'
        read_only_fields = ['employee', 'uploaded_at']

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url


class OnboardingChecklistSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = OnboardingChecklist
        fields = '__all__'
        read_only_fields = ['employee', 'completed_at']


class ExitManagementSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.code', read_only=True)
    reason_label = serializers.CharField(source='get_reason_display', read_only=True)

    class Meta:
        model = ExitManagement
        fields = '__all__'
