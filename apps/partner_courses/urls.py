from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('', views.list_partner_courses, name='partner-courses-list'),

    # Admin (is_staff only)
    path('admin/', views.admin_list_partner_courses, name='partner-courses-admin-list'),
    path('admin/create/', views.create_partner_course, name='partner-courses-admin-create'),
    path('admin/<int:course_id>/', views.update_partner_course, name='partner-courses-admin-update'),
]
