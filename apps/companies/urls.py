from django.urls import path

from .views import (
    CompanyListView, CompanyDetailView, CompanyUsersView, SwitchCompanyView, MyCompanyView,
)

urlpatterns = [
    path('companies/', CompanyListView.as_view()),
    path('companies/<int:company_id>/', CompanyDetailView.as_view()),
    path('companies/<int:company_id>/users/', CompanyUsersView.as_view()),
    path('companies/switch/', SwitchCompanyView.as_view()),
    path('my-company/', MyCompanyView.as_view()),
]
