from django.urls import path
from . import views

urlpatterns = [
    path('apply/', views.apply, name='affiliate-apply'),
    path('check-code/', views.check_code_availability, name='affiliate-check-code'),
    path('dashboard/', views.affiliate_dashboard, name='affiliate-dashboard'),
    path('links/', views.affiliate_links, name='affiliate-links'),
    path('commissions/', views.affiliate_commissions, name='affiliate-commissions'),
    path('bank-details/', views.affiliate_bank_details, name='affiliate-bank-details'),
    path('track/<str:code>/', views.track_click, name='affiliate-track-click'),

    path('admin/list/', views.admin_list_affiliates, name='affiliate-admin-list'),
    path('admin/<int:affiliate_id>/detail/', views.admin_affiliate_detail, name='affiliate-admin-detail'),
    path('admin/<int:affiliate_id>/approve/', views.admin_approve_affiliate, name='affiliate-admin-approve'),
    path('admin/<int:affiliate_id>/reject/', views.admin_reject_affiliate, name='affiliate-admin-reject'),
    path('admin/<int:affiliate_id>/commission/', views.admin_set_commission, name='affiliate-admin-commission'),
    path('admin/<int:affiliate_id>/delete/', views.admin_delete_affiliate, name='affiliate-admin-delete'),
    path('admin/commissions/', views.admin_list_commissions, name='affiliate-admin-commissions'),
    path('admin/commissions/<int:commission_id>/pay/', views.admin_mark_commission_paid, name='affiliate-admin-commission-pay'),
]
