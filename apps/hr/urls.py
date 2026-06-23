from rest_framework.routers import DefaultRouter
from .views import DepartmentViewSet, EmployeeViewSet, AttendanceViewSet, LeaveRequestViewSet

app_name = 'hr'
router = DefaultRouter()
router.register('departments', DepartmentViewSet, basename='department')
router.register('employees', EmployeeViewSet, basename='employee')
router.register('attendance', AttendanceViewSet, basename='attendance')
router.register('leave-requests', LeaveRequestViewSet, basename='leave-request')

urlpatterns = router.urls
