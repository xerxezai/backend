from django.urls import path
from .views import (
    ContactMessageCreateView,
    ContactInquiryListView, ContactInquiryDetailView, ContactInquiryStatsView,
)

app_name = 'contact'

urlpatterns = [
    path('', ContactMessageCreateView.as_view(), name='contact-submit'),

    # Contact Inquiries admin (super_admin only)
    path('inquiries/', ContactInquiryListView.as_view()),
    path('inquiries/stats/', ContactInquiryStatsView.as_view()),
    path('inquiries/<int:pk>/', ContactInquiryDetailView.as_view()),
]
