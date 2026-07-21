from django.urls import path

from .views import PartnerApplyView, PartnerApplicationListView, PartnerApplicationDetailView

urlpatterns = [
    path('apply/', PartnerApplyView.as_view()),
    path('applications/', PartnerApplicationListView.as_view()),
    path('applications/<int:pk>/', PartnerApplicationDetailView.as_view()),
]
