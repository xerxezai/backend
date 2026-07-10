from rest_framework.routers import DefaultRouter

from .views import (AttendanceViewSet, DepartmentViewSet, EmployeeViewSet,
                    LeaveRequestViewSet, PaySlipViewSet, PayrollViewSet,
                    SalaryStructureViewSet, ShiftViewSet,
                    PerformanceReviewViewSet, EmployeeDocumentViewSet,
                    OnboardingChecklistViewSet, ExitManagementViewSet)

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

# Added HR features
router.register('reviews', PerformanceReviewViewSet, basename='review')
router.register('documents', EmployeeDocumentViewSet, basename='document')
router.register('onboarding', OnboardingChecklistViewSet, basename='onboarding')
router.register('exit', ExitManagementViewSet, basename='exit')

urlpatterns = router.urls
