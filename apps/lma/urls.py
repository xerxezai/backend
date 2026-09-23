from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Auth
    path('auth/login/', views.lma_login, name='lma-login'),
    path('auth/register/', views.lma_register, name='lma-register'),
    # TokenRefreshView only validates the refresh token itself (SimpleJWT's
    # own signature/expiry check), same as apps/authentication/urls.py —
    # takes {"refresh": "..."} and returns a fresh {"access": "..."}.
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='lma-token-refresh'),

    # Courses (public + browse)
    path('courses/', views.course_list, name='lma-course-list'),
    path('courses/browse/', views.browse_courses, name='lma-browse-courses'),
    path('courses/create/', views.create_course, name='lma-create-course'),
    path('courses/<int:course_id>/', views.course_detail, name='lma-course-detail'),
    path('courses/<int:course_id>/update/', views.update_course, name='lma-update-course'),
    path('courses/<int:course_id>/delete/', views.delete_course, name='lma-delete-course'),
    path('courses/<int:course_id>/modules/', views.course_modules, name='lma-course-modules'),
    path('courses/<int:course_id>/create-order/', views.create_order, name='lma-create-order'),
    path('courses/<int:course_id>/verify-payment/', views.verify_payment, name='lma-verify-payment'),
    path('courses/<int:course_id>/submit-for-review/', views.submit_for_review, name='lma-submit-for-review'),
    path('courses/<int:course_id>/publish/', views.publish_course, name='lma-publish-course'),
    path('courses/<int:course_id>/reject/', views.reject_course, name='lma-reject-course'),
    path('courses/<int:course_id>/review/', views.submit_review, name='lma-submit-review'),
    path('courses/<int:course_id>/my-review/', views.my_review_for_course, name='lma-my-review'),
    path('courses/<int:course_id>/reviews/', views.course_reviews, name='lma-course-reviews'),
    path('courses/<int:course_id>/upload-certificate-template/', views.upload_course_certificate_template, name='lma-upload-certificate-template'),
    path('courses/<int:course_id>/certificate-template/', views.get_course_certificate_template, name='lma-certificate-template'),
    path('courses/<int:course_id>/generate-certificate/', views.generate_certificate, name='lma-generate-certificate'),

    # Modules
    path('modules/<int:module_id>/', views.module_detail_view, name='lma-module-detail'),
    path('modules/<int:module_id>/lessons/', views.module_lessons, name='lma-module-lessons'),

    # Lessons
    path('lessons/<int:lesson_id>/', views.lesson_detail_view, name='lma-lesson-detail'),
    path('lessons/<int:lesson_id>/video/', views.lesson_video_url, name='lma-lesson-video'),
    path('lessons/<int:lesson_id>/player/', views.lesson_player_content, name='lma-lesson-player'),
    path('lessons/<int:lesson_id>/complete/', views.lesson_complete, name='lma-lesson-complete'),
    path('lessons/<int:lesson_id>/upload-video/', views.upload_lesson_video, name='lma-upload-lesson-video'),
    path('lessons/<int:lesson_id>/upload-document/', views.upload_lesson_document, name='lma-upload-lesson-document'),
    path('lessons/<int:lesson_id>/quiz/', views.lesson_quiz, name='lma-lesson-quiz'),
    path('lessons/<int:lesson_id>/quiz/submit/', views.submit_quiz, name='lma-submit-quiz'),
    path('lessons/<int:lesson_id>/assignment/', views.lesson_assignment, name='lma-lesson-assignment'),
    # Named lesson-assignments (not assignments/) — the plain "assignments/<id>/submit/"
    # path below already belongs to the older, course-level Assignment/Submission flow.
    path('lesson-assignments/<int:assignment_id>/submit/', views.submit_lesson_assignment, name='lma-submit-lesson-assignment'),

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
    path('certificates/<int:certificate_id>/download/', views.download_certificate, name='lma-download-certificate'),

    # Profile
    path('profile/', views.lma_profile, name='lma-profile'),
    path('profile/change-password/', views.change_password, name='lma-change-password'),

    # Instructor
    path('instructor/dashboard/', views.instructor_dashboard, name='lma-instructor-dashboard'),
    path('instructor/courses/', views.instructor_courses, name='lma-instructor-courses'),
    path('instructor/students/', views.instructor_students, name='lma-instructor-students'),
    path('instructor/students/<int:student_id>/details/', views.student_detail, name='lma-student-detail'),
    path('instructor/enrollments/<int:enrollment_id>/', views.unenroll_student, name='lma-unenroll-student'),
    path('instructor/reviews/', views.instructor_reviews, name='lma-instructor-reviews'),
    path('instructor/analytics/', views.instructor_analytics, name='lma-instructor-analytics'),
    path('instructor/instructors/', views.instructor_list, name='lma-instructor-list'),
    path('instructor/instructors/<int:instructor_id>/', views.update_instructor, name='lma-update-instructor'),
    path('instructor/instructors/<int:instructor_id>/delete/', views.delete_instructor, name='lma-delete-instructor'),
    path('instructor/instructors/<int:instructor_id>/courses/', views.instructor_course_list, name='lma-instructor-course-list'),
    path('instructor/instructors/<int:instructor_id>/reset-password/', views.reset_instructor_password, name='lma-reset-instructor-password'),
    path('instructor/create-instructor/', views.create_instructor, name='lma-create-instructor'),
    path('instructor/pending-reviews/', views.pending_review_queue, name='lma-pending-reviews'),

    # Notifications
    path('notifications/', views.list_notifications, name='lma-notifications'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_read, name='lma-notification-read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='lma-notifications-read-all'),

    # Assignments
    path('assignments/<int:assignment_id>/submit/', views.submit_assignment, name='lma-submit-assignment'),
    path('submissions/<int:submission_id>/grade/', views.grade_submission, name='lma-grade-submission'),

    # Instructor Applications
    path('become-instructor/', views.become_instructor, name='lma-become-instructor'),
    path('instructor/applications/', views.list_applications, name='lma-applications'),
    path('instructor/applications/<int:app_id>/approve/', views.approve_application, name='lma-approve-application'),
    path('instructor/applications/<int:app_id>/reject/', views.reject_application, name='lma-reject-application'),

    # Admin (is_staff / is_superuser only) — cross-instructor visibility
    path('admin/students/', views.admin_students, name='lma-admin-students'),
    path('admin/enrollments/', views.admin_enrollments, name='lma-admin-enrollments'),
    path('admin/analytics/', views.admin_course_analytics, name='lma-admin-analytics'),
    path('admin/users/', views.admin_users, name='lma-admin-users'),
    path('admin/users/create/', views.admin_create_user, name='lma-admin-create-user'),
    path('admin/users/<int:user_id>/', views.admin_user_detail, name='lma-admin-user-detail'),
    path('admin/pending-courses/', views.pending_review_queue, name='lma-admin-pending-courses'),
    path('admin/courses/<int:course_id>/approve/', views.publish_course, name='lma-admin-approve-course'),
    path('admin/courses/<int:course_id>/reject/', views.reject_course, name='lma-admin-reject-course'),
]
