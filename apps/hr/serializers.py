from rest_framework import serializers
from .models import Department, Employee, Attendance, LeaveRequest, Shift, SalaryStructure, Payroll, PaySlip


class DepartmentSerializer(serializers.ModelSerializer):
    manager_username = serializers.CharField(source='manager.username', read_only=True)

    class Meta:
        model = Department
        fields = '__all__'


class EmployeeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Employee
        fields = '__all__'


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
