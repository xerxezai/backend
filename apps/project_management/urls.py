from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ProjectViewSet, MilestoneViewSet, TaskViewSet, BudgetEntryViewSet

router = DefaultRouter()
router.register('projects', ProjectViewSet, basename='project')
router.register('milestones', MilestoneViewSet, basename='milestone')
router.register('tasks', TaskViewSet, basename='task')
router.register('budget-entries', BudgetEntryViewSet, basename='budgetentry')

urlpatterns = [
    path('', include(router.urls)),
]
