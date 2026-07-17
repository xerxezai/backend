from django.urls import path

from .views import (
    ModuleListView, MyAccessView, UserManagementView, UserDetailView,
    GrantAccessView, AccessRequestView, AccessRequestActionView,
)

urlpatterns = [
    path('modules/', ModuleListView.as_view()),
    path('my-access/', MyAccessView.as_view()),
    path('users/', UserManagementView.as_view()),
    path('users/create/', UserManagementView.as_view()),
    path('users/<int:user_id>/', UserDetailView.as_view()),
    path('users/<int:user_id>/grant-access/', GrantAccessView.as_view()),
    path('users/<int:user_id>/revoke-access/', GrantAccessView.as_view()),
    path('access-requests/', AccessRequestView.as_view()),
    path('access-requests/<int:request_id>/<str:action>/', AccessRequestActionView.as_view()),
]
