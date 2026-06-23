"""
MLM URL configuration for XERXEZ Backend
Base path: /api/v1/mlm/
"""

from django.urls import path
from . import views

app_name = 'mlm'

urlpatterns = [
    # Profile registration & listing
    path('profile/', views.MLMProfileListCreateView.as_view(), name='profile-list-create'),
    path('profile/<int:pk>/', views.MLMProfileDetailView.as_view(), name='profile-detail'),

    # Commission structure (admin)
    path('commission-structure/', views.CommissionStructureListCreateView.as_view(), name='commission-structure-list'),
    path('commission-structure/<int:pk>/', views.CommissionStructureDetailView.as_view(), name='commission-structure-detail'),

    # Transactions
    path('transactions/', views.TransactionListCreateView.as_view(), name='transaction-list'),
    path('transactions/<int:pk>/', views.TransactionDetailView.as_view(), name='transaction-detail'),

    # Commissions earned
    path('commissions/', views.CommissionListView.as_view(), name='commission-list'),

    # Earnings summary
    path('earnings/', views.EarningsView.as_view(), name='earnings'),

    # Referral tree (nested JSON)
    path('tree/', views.referral_tree_view, name='referral-tree'),

    # Dashboard summary
    path('dashboard/', views.dashboard_view, name='dashboard'),
]
