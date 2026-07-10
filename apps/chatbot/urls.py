from django.urls import path
from .views import ChatbotMessageView

app_name = 'chatbot'

urlpatterns = [
    path('message/', ChatbotMessageView.as_view(), name='chatbot-message'),
]
