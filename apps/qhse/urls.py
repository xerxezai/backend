from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    IncidentViewSet, InspectionViewSet, RiskRegisterViewSet,
    SafetyChecklistViewSet, ChecklistItemViewSet, ComplianceRecordViewSet, QHSEDashboardView,
)

router = DefaultRouter()
router.register('incidents', IncidentViewSet, basename='incident')
router.register('inspections', InspectionViewSet, basename='inspection')
router.register('risks', RiskRegisterViewSet, basename='risk')
router.register('checklists', SafetyChecklistViewSet, basename='safetychecklist')
router.register('checklist-items', ChecklistItemViewSet, basename='checklistitem')
router.register('compliance', ComplianceRecordViewSet, basename='compliancerecord')

urlpatterns = [
    path('dashboard/', QHSEDashboardView.as_view(), name='qhse-dashboard'),
    path('', include(router.urls)),
]
