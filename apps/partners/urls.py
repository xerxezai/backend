from django.urls import path

from .views import (
    PartnerApplyView, PartnerLoginView, PartnerMeView, PartnerDashboardView,
    PartnerDealListCreateView, PartnerDealDetailView, PartnerMaterialsView,
    AdminPartnerListView, AdminPartnerDetailView, AdminPartnerApproveView, AdminPartnerRejectView,
    AdminDealListView, AdminDealDetailView,
)

urlpatterns = [
    # Public application
    path('apply/', PartnerApplyView.as_view()),

    # Partner portal (JWT auth, real Django user account created on approval)
    path('login/', PartnerLoginView.as_view()),
    path('me/', PartnerMeView.as_view()),
    path('dashboard/', PartnerDashboardView.as_view()),
    path('deals/', PartnerDealListCreateView.as_view()),
    path('deals/<int:pk>/', PartnerDealDetailView.as_view()),
    path('materials/', PartnerMaterialsView.as_view()),

    # Admin (super_admin only) — mounted under this app's own prefix rather than a
    # standalone '/api/admin/partners/' to match this codebase's single '/api/v1/'
    # prefix convention (see xerxez_backend/urls.py).
    path('admin/partners/', AdminPartnerListView.as_view()),
    path('admin/partners/<int:pk>/', AdminPartnerDetailView.as_view()),
    path('admin/partners/<int:pk>/approve/', AdminPartnerApproveView.as_view()),
    path('admin/partners/<int:pk>/reject/', AdminPartnerRejectView.as_view()),
    path('admin/deals/', AdminDealListView.as_view()),
    path('admin/deals/<int:pk>/', AdminDealDetailView.as_view()),
]
