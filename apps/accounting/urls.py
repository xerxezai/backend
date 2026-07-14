from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AccountViewSet, JournalEntryViewSet, JournalLineViewSet, ExpenseViewSet,
    TaxReportView, BalanceSheetView, AccountingDashboardView,
)

app_name = 'accounting'
router = DefaultRouter()
router.register('accounts', AccountViewSet, basename='account')
router.register('journal-entries', JournalEntryViewSet, basename='journal-entry')
router.register('journal-lines', JournalLineViewSet, basename='journal-line')
router.register('expenses', ExpenseViewSet, basename='expense')

urlpatterns = [
    path('tax-report/', TaxReportView.as_view(), name='tax-report'),
    path('balance-sheet/', BalanceSheetView.as_view(), name='balance-sheet'),
    path('dashboard/', AccountingDashboardView.as_view(), name='accounting-dashboard'),
] + router.urls
