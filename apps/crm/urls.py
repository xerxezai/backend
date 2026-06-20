from django.urls import path
from rest_framework.routers import DefaultRouter

app_name = 'crm'
router = DefaultRouter()

urlpatterns = [] + router.urls
