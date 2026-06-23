from rest_framework import viewsets, filters
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Department, Employee, Attendance, LeaveRequest
from .serializers import DepartmentSerializer, EmployeeSerializer, AttendanceSerializer, LeaveRequestSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code']


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related('department', 'user').all()
    serializer_class = EmployeeSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['full_name', 'email', 'code']
    filterset_fields = ['department', 'status']


class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.select_related('employee').all()
    serializer_class = AttendanceSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['employee', 'date']
    ordering_fields = ['date']


class LeaveRequestViewSet(viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.select_related('employee', 'decided_by').all()
    serializer_class = LeaveRequestSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'status', 'type']
