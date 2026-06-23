from rest_framework import serializers
from .models import Department, Employee, Attendance, LeaveRequest


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
