from django.urls import path

from .views import (
    PartnerApplyView, PartnerApplicationListView, PartnerApplicationDetailView,
    PartnerLoginView, PartnerMeView, PartnerLeadListCreateView,
)

urlpatterns = [
    path('apply/', PartnerApplyView.as_view()),
    path('applications/', PartnerApplicationListView.as_view()),
    path('applications/<int:pk>/', PartnerApplicationDetailView.as_view()),
    # Partner Portal (email + access-code auth via headers, not JWT — see utils.py)
    path('login/', PartnerLoginView.as_view()),
    path('me/', PartnerMeView.as_view()),
    path('leads/', PartnerLeadListCreateView.as_view()),
]
