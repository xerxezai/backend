from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('auth/login/', views.lma_login, name='lma-login'),
    path('auth/register/', views.lma_register, name='lma-register'),

    # Courses (public + browse)
    path('courses/', views.course_list, name='lma-course-list'),
    path('courses/browse/', views.browse_courses, name='lma-browse-courses'),
    path('courses/create/', views.create_course, name='lma-create-course'),
    path('courses/<int:course_id>/', views.course_detail, name='lma-course-detail'),
    path('courses/<int:course_id>/update/', views.update_course, name='lma-update-course'),
    path('courses/<int:course_id>/delete/', views.delete_course, name='lma-delete-course'),
    path('courses/<int:course_id>/modules/', views.course_modules, name='lma-course-modules'),

    # Modules
    path('modules/<int:module_id>/', views.module_detail_view, name='lma-module-detail'),
    path('modules/<int:module_id>/lessons/', views.module_lessons, name='lma-module-lessons'),

    # Lessons
    path('lessons/<int:lesson_id>/', views.lesson_detail_view, name='lma-lesson-detail'),
    path('lessons/<int:lesson_id>/complete/', views.lesson_complete, name='lma-lesson-complete'),

    # Enrollment
    path('enroll/<int:course_id>/', views.enroll, name='lma-enroll'),
    path('mock-payment/<int:course_id>/', views.mock_payment, name='lma-mock-payment'),
    path('enrollment-status/<int:course_id>/', views.enrollment_status, name='lma-enrollment-status'),

    # Student
    path('student/dashboard/', views.student_dashboard, name='lma-student-dashboard'),
    path('student/my-courses/', views.my_courses, name='lma-my-courses'),
    path('student/assignments/', views.my_assignments, name='lma-my-assignments'),
    path('student/progress/', views.my_progress, name='lma-my-progress'),
    path('certificates/', views.my_certificates, name='lma-certificates'),

    # Profile
    path('profile/', views.lma_profile, name='lma-profile'),
    path('profile/change-password/', views.change_password, name='lma-change-password'),

    # Instructor
    path('instructor/dashboard/', views.instructor_dashboard, name='lma-instructor-dashboard'),
    path('instructor/courses/', views.instructor_courses, name='lma-instructor-courses'),
    path('instructor/students/', views.instructor_students, name='lma-instructor-students'),
    path('instructor/reviews/', views.instructor_reviews, name='lma-instructor-reviews'),
    path('instructor/analytics/', views.instructor_analytics, name='lma-instructor-analytics'),

    # Assignments
    path('assignments/<int:assignment_id>/submit/', views.submit_assignment, name='lma-submit-assignment'),
    path('submissions/<int:submission_id>/grade/', views.grade_submission, name='lma-grade-submission'),
]
