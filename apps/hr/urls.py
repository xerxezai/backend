from rest_framework.routers import DefaultRouter

from .views import (AttendanceViewSet, DepartmentViewSet, EmployeeViewSet,
                    LeaveRequestViewSet, PaySlipViewSet, PayrollViewSet,
                    SalaryStructureViewSet, ShiftViewSet)

app_name = 'hr'
router = DefaultRouter()

# Existing routes (preserved)
router.register('departments', DepartmentViewSet, basename='department')
router.register('employees', EmployeeViewSet, basename='employee')
router.register('attendance', AttendanceViewSet, basename='attendance')
router.register('leave-requests', LeaveRequestViewSet, basename='leave-request')

# New routes
router.register('shifts', ShiftViewSet, basename='shift')
router.register('salary-structures', SalaryStructureViewSet, basename='salary-structure')
router.register('payroll', PayrollViewSet, basename='payroll')
router.register('payslips', PaySlipViewSet, basename='payslip')

urlpatterns = router.urls
