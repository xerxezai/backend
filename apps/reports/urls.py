from django.urls import path
from .views import ERPDashboardView, SalesReportView, HRReportView, InventoryReportView

app_name = 'reports'
urlpatterns = [
    path('dashboard/', ERPDashboardView.as_view(), name='erp-dashboard'),
    path('sales/', SalesReportView.as_view(), name='sales-report'),
    path('hr/', HRReportView.as_view(), name='hr-report'),
    path('inventory/', InventoryReportView.as_view(), name='inventory-report'),
]
