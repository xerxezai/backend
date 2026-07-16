from django.urls import path

from .views import CareerApplyView, CareerPositionsView

app_name = 'careers'

urlpatterns = [
    path('apply/', CareerApplyView.as_view(), name='careers-apply'),
    path('positions/', CareerPositionsView.as_view(), name='careers-positions'),
]
