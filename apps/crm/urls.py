from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    CustomerViewSet, ContactViewSet, LeadViewSet, ActivityViewSet,
    DealViewSet, CustomerNoteViewSet, PipelineView, CRMDashboardView,
)

app_name = 'crm'
router = DefaultRouter()
router.register('customers', CustomerViewSet, basename='customer')
router.register('contacts', ContactViewSet, basename='contact')
router.register('leads', LeadViewSet, basename='lead')
router.register('activities', ActivityViewSet, basename='activity')
router.register('deals', DealViewSet, basename='deal')
router.register('notes', CustomerNoteViewSet, basename='note')

urlpatterns = [
    path('pipeline/', PipelineView.as_view(), name='pipeline'),
    path('dashboard/', CRMDashboardView.as_view(), name='crm-dashboard'),
] + router.urls
