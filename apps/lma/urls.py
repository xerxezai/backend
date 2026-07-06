from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('auth/login/', views.lma_login, name='lma-login'),

    # Courses (public)
    path('courses/', views.course_list, name='lma-course-list'),
    path('courses/<int:course_id>/', views.course_detail, name='lma-course-detail'),

    # Enrollment
    path('enroll/<int:course_id>/', views.enroll, name='lma-enroll'),
    path('mock-payment/<int:course_id>/', views.mock_payment, name='lma-mock-payment'),

    # Student
    path('student/dashboard/', views.student_dashboard, name='lma-student-dashboard'),
    path('certificates/', views.my_certificates, name='lma-certificates'),

    # Instructor
    path('instructor/dashboard/', views.instructor_dashboard, name='lma-instructor-dashboard'),
    path('courses/create/', views.create_course, name='lma-create-course'),
    path('courses/<int:course_id>/update/', views.update_course, name='lma-update-course'),

    # Lessons
    path('lessons/<int:lesson_id>/complete/', views.lesson_complete, name='lma-lesson-complete'),

    # Assignments
    path('assignments/<int:assignment_id>/submit/', views.submit_assignment, name='lma-submit-assignment'),
    path('submissions/<int:submission_id>/grade/', views.grade_submission, name='lma-grade-submission'),
]
