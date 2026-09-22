"""
LMA (Learning Management Application) Views
"""
import logging

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings as django_settings
from django.db import transaction
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes, parser_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle


class IsLMAAdmin(BasePermission):
    """Gates the LMA admin endpoints (all students / all enrollments) — Django
    staff or superuser only. Deliberately separate from can_access_instructor:
    an instructor should not automatically see every student across every
    other instructor's courses."""
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))

from apps.core.email import send_via_resend
from apps.core.sanitize import clean_text
from apps.core.throttles import LoginRateThrottle
from apps.core.audit import log_audit_event


class BecomeInstructorRateThrottle(AnonRateThrottle):
    scope = 'become_instructor'
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)

from .models import (
    LMAProfile, Course, Module, Lesson, Enrollment, Assignment,
    Submission, Certificate, Review, LessonProgress, Notification,
    InstructorApplication,
    Quiz, QuizQuestion, QuizAttempt, LessonAssignment, LessonAssignmentSubmission,
)
from .serializers import (
    CourseListSerializer, CourseDetailSerializer, EnrollmentSerializer,
    AssignmentSerializer, SubmissionSerializer, CertificateSerializer,
    ReviewSerializer, CourseCreateSerializer,
    ModuleSerializer, ModuleWriteSerializer,
    LessonDetailSerializer, LessonWriteSerializer,
    QuizSerializer, QuizStudentSerializer, QuizQuestionSerializer, QuizAttemptSerializer,
    LessonAssignmentSerializer, LessonAssignmentSubmissionSerializer,
)
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.http import FileResponse

from .certificate_utils import generate_certificate_file, TemplateNotRenderable
from apps.affiliates.services import record_conversion_from_cookie as _record_affiliate_conversion

User = get_user_model()

INSTRUCTOR_USERNAMES = {'danish', 'tanzeem'}
INSTRUCTOR_EMAILS    = {
    'danish@xerxez.com',
    'tanzeem@xerxez.com',
    'xerxez.in@gmail.com',
}
SUPER_INSTRUCTOR_EMAILS = ['danish@xerxez.com', 'tanzeem@xerxez.com']


import re as _re


def _get_or_create_lma_profile(user):
    profile, _ = LMAProfile.objects.get_or_create(user=user)
    is_super = (
        user.username.lower() in INSTRUCTOR_USERNAMES or
        user.email.lower() in INSTRUCTOR_EMAILS
    )
    if is_super:
        profile.lma_role = 'both'
        profile.can_access_student = True
        profile.can_access_instructor = True
        profile.instructor_level = 'super'
        profile.save()
    return profile


def _is_super(profile) -> bool:
    return profile.can_access_instructor and profile.instructor_level == 'super'


def _is_instructor_admin(user, profile) -> bool:
    """True for super instructors (existing instructor_level='super' tier,
    unchanged) AND the newer is_staff-based 'Instructor Admin' tier — an
    instructor-role account with is_staff=True. Grants access to the
    Instructors + Applications ADMIN pages only; Earnings, Pending Reviews
    and revenue Analytics stay gated by _is_super alone. Requires
    can_access_instructor so a Student Admin (is_staff=True, lma_role=
    'student', can_access_instructor=False) can never qualify via is_staff
    alone."""
    return _is_super(profile) or (profile.can_access_instructor and user.is_staff)


def _is_lma_admin_or_super(user, profile) -> bool:
    """True for super instructors OR any Django staff/superuser account (the
    same IsLMAAdmin check gating admin/students, admin/enrollments,
    admin/analytics) — used by the course-approval endpoints so the admin
    "Pending Courses" page works for admins who aren't instructors at all,
    not just super instructors."""
    return _is_super(profile) or user.is_staff or user.is_superuser


def _lma_token(user):
    """Issues both an access and a refresh token — same pattern as ERP's
    LoginView — so the frontend can silently renew a session instead of
    hard-logging-out every ACCESS_TOKEN_LIFETIME."""
    refresh = RefreshToken.for_user(user)
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


def _send_safe(subject, message, recipient_list):
    """send_mail wrapped so email failures never break the main request.
    Skips the attempt entirely (with a warning, not an error) when
    EMAIL_HOST_USER isn't configured — an empty SMTP username means the
    connection can't succeed anyway, so there's no point trying and
    surfacing an avoidable connection-refused/auth-failed traceback."""
    if not django_settings.EMAIL_HOST_USER:
        logger.warning('LMA email skipped (EMAIL_HOST_USER not configured): %s', subject)
        return
    try:
        from_email = getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'info@xerxez.com')
        send_mail(subject, message, from_email, recipient_list, fail_silently=True)
    except Exception as exc:
        logger.warning('LMA email failed: %s', exc)


# ── Resend notification emails ───────────────────────────────────────────────
# TEMPORARY: xerxez.com is not yet verified in Resend, so sends must use
# Resend's shared onboarding@resend.dev sender until domain verification
# completes. Switch to CONTACT_FROM_EMAIL (info@xerxez.com) once verified.
LMA_FROM_EMAIL = 'onboarding@resend.dev'
LMA_ADMIN_EMAIL = getattr(django_settings, 'CONTACT_ADMIN_EMAIL', 'info@xerxez.com')

_EMAIL_STYLE = """
  body{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}
  .wrap{max-width:580px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;
        box-shadow:0 4px 32px rgba(0,0,0,.10)}
  .hdr{background:#1a1a1a;padding:36px 40px;text-align:center}
  .hdr h1{color:#D4A853;font-family:Georgia,serif;font-size:22px;margin:0 0 4px;letter-spacing:.04em}
  .hdr p{color:rgba(255,255,255,.55);font-size:13px;margin:0}
  .body{padding:36px 40px;font-size:14px;color:#333;line-height:1.74}
  .detail-box{background:#fafaf8;border-radius:10px;border:1px solid #f0ede8;border-left:3px solid #D4A853;
              padding:16px 20px;margin:20px 0;font-size:13px}
  .detail-box p{margin:4px 0;color:#5a5650}
  .detail-box strong{color:#1a1a1a}
  .ftr{background:#1a1a1a;border-top:1px solid #2c2c2c;padding:18px 40px;
       text-align:center;font-size:12px;color:rgba(255,255,255,.45)}
"""


def _lma_email_shell(heading: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><style>{_EMAIL_STYLE}</style></head>
<body>
<div class="wrap">
  <div class="hdr"><h1>XERXEZ</h1><p>{heading}</p></div>
  <div class="body">{body_html}</div>
  <div class="ftr">XERXEZ Academy &nbsp;·&nbsp; info@xerxez.com &nbsp;·&nbsp; xerxez.com</div>
</div>
</body>
</html>"""


def _send_enrollment_emails(student, course):
    """Welcome email to the student + notification to the XERXEZ team."""
    first = student.get_full_name() or student.username

    student_plain = (
        f"Hi {first},\n\n"
        f"You're enrolled in \"{course.title}\"! Head to your student dashboard to start learning.\n\n"
        f"Best regards,\nThe XERXEZ Academy Team\ninfo@xerxez.com | xerxez.com"
    )
    student_html = _lma_email_shell("Enterprise AI & ERP Solutions", f"""
      <p>Hi {first},</p>
      <p>You're enrolled in <strong>{course.title}</strong>! Head to your student dashboard to start learning.</p>
      <div class="detail-box">
        <p><strong>Course:</strong> {course.title}</p>
        <p><strong>Category:</strong> {course.category}</p>
        <p><strong>Level:</strong> {course.get_level_display()}</p>
      </div>
      <p>Best regards,<br><strong>The XERXEZ Academy Team</strong></p>
    """)
    send_via_resend(
        to=student.email, subject=f"Welcome to {course.title}!",
        html=student_html, text=student_plain, from_email=LMA_FROM_EMAIL,
    )

    admin_plain = (
        f"New enrollment on XERXEZ Academy\n"
        f"Student : {first} ({student.email})\n"
        f"Course  : {course.title}\n"
    )
    admin_html = _lma_email_shell("New Student Enrollment", f"""
      <p>A new student has enrolled.</p>
      <div class="detail-box">
        <p><strong>Student:</strong> {first} ({student.email})</p>
        <p><strong>Course:</strong> {course.title}</p>
      </div>
    """)
    send_via_resend(
        to=LMA_ADMIN_EMAIL, subject=f"New Student Enrollment - {course.title}",
        html=admin_html, text=admin_plain, from_email=LMA_FROM_EMAIL, reply_to=student.email,
    )


def _send_completion_email(student, course):
    first = student.get_full_name() or student.username
    plain = (
        f"Congratulations {first}!\n\n"
        f"You've completed \"{course.title}\". Your certificate is now available on your student dashboard.\n\n"
        f"Best regards,\nThe XERXEZ Academy Team\ninfo@xerxez.com | xerxez.com"
    )
    html = _lma_email_shell("Course Completed", f"""
      <p>Congratulations {first}!</p>
      <p>You've completed <strong>{course.title}</strong>. Your certificate is now available on your student dashboard.</p>
      <p>Best regards,<br><strong>The XERXEZ Academy Team</strong></p>
    """)
    send_via_resend(
        to=student.email, subject=f"Congratulations! You completed {course.title}",
        html=html, text=plain, from_email=LMA_FROM_EMAIL,
    )


def _send_instructor_assigned_email(instructor, course):
    first = instructor.get_full_name() or instructor.username
    plain = (
        f"Hi {first},\n\n"
        f"You've been assigned as the instructor for \"{course.title}\". "
        f"You can manage it from your instructor dashboard.\n\n"
        f"Best regards,\nThe XERXEZ Academy Team\ninfo@xerxez.com | xerxez.com"
    )
    html = _lma_email_shell("Instructor Assignment", f"""
      <p>Hi {first},</p>
      <p>You've been assigned as the instructor for <strong>{course.title}</strong>. You can manage it from your instructor dashboard.</p>
      <div class="detail-box">
        <p><strong>Course:</strong> {course.title}</p>
        <p><strong>Category:</strong> {course.category}</p>
      </div>
      <p>Best regards,<br><strong>The XERXEZ Academy Team</strong></p>
    """)
    send_via_resend(
        to=instructor.email, subject=f"You've been assigned to teach {course.title}",
        html=html, text=plain, from_email=LMA_FROM_EMAIL,
    )


# ── Auth ────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def lma_login(request):
    """POST /api/v1/lma/auth/login/"""
    email = request.data.get('email', '').strip()
    password = request.data.get('password', '')
    role = request.data.get('role', 'student')

    if not email or not password:
        return Response({'error': 'Email and password are required.'}, status=400)

    email_lower = email.lower()
    user = None
    try:
        user = User.objects.get(email__iexact=email_lower)
    except User.DoesNotExist:
        try:
            user = User.objects.get(username__iexact=email_lower)
        except User.DoesNotExist:
            pass
    except User.MultipleObjectsReturned:
        user = User.objects.filter(email__iexact=email_lower).first()

    if not user or not user.check_password(password):
        log_audit_event(request, 'login_failure', username=email, source='lma')
        return Response({'error': 'Invalid credentials.'}, status=401)

    if not user.is_active:
        log_audit_event(request, 'login_failure', username=email, source='lma')
        return Response({'error': 'Account is inactive.'}, status=401)

    profile = _get_or_create_lma_profile(user)

    if role == 'instructor' and not profile.can_access_instructor:
        return Response(
            {'error': "You don't have instructor access. Contact admin to request access."},
            status=403,
        )

    log_audit_event(request, 'login_success', username=user.username, source='lma')
    token = _lma_token(user)
    name = user.get_full_name() or user.username
    affiliate = getattr(user, 'affiliate', None)

    return Response({
        'lma_token': token['access'],
        'lma_refresh': token['refresh'],
        'lma_role': role,
        'can_access_student': profile.can_access_student,
        'can_access_instructor': profile.can_access_instructor,
        'instructor_level': profile.instructor_level,
        'name': name,
        'user_id': user.id,
        'is_affiliate': bool(affiliate and affiliate.status == 'approved'),
        'affiliate_status': affiliate.status if affiliate else None,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def lma_register(request):
    """POST /api/v1/lma/auth/register/"""
    name = request.data.get('name', '').strip()
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')

    if not name or not email or not password:
        return Response({'error': 'Name, email and password are required.'}, status=400)
    if len(password) < 6:
        return Response({'error': 'Password must be at least 6 characters.'}, status=400)
    if not _re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return Response({'error': 'Enter a valid email address.'}, status=400)
    if User.objects.filter(email=email).exists():
        return Response({'error': 'An account with this email already exists.'}, status=400)

    base = _re.sub(r'[^a-z0-9_]', '', email.split('@')[0]) or 'user'
    username, n = base, 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{n}"; n += 1

    parts = name.split(' ', 1)
    try:
        with transaction.atomic():
            user = User(
                username=username, email=email,
                first_name=parts[0], last_name=parts[1] if len(parts) > 1 else '',
                is_active=True,
            )
            user.set_password(password)
            user._skip_profile_signal = True
            user.save()

            profile, _ = LMAProfile.objects.get_or_create(
                user=user,
                defaults={
                    'lma_role': 'student',
                    'can_access_student': True,
                    'can_access_instructor': False,
                    'bio': '',
                },
            )
            if profile.lma_role not in ('instructor', 'both'):
                profile.lma_role = 'student'
            profile.can_access_student = True
            profile.save()
    except Exception as exc:
        return Response({'error': f'Could not create account: {exc}'}, status=400)

    reg_token = _lma_token(user)
    return Response({
        'lma_token': reg_token['access'],
        'lma_refresh': reg_token['refresh'],
        'lma_role': 'student',
        'can_access_student': True,
        'can_access_instructor': profile.can_access_instructor,
        'instructor_level': profile.instructor_level,
        'name': name,
        'user_id': user.id,
    }, status=201)


# ── Courses (public) ────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def course_list(request):
    """GET /api/v1/lma/courses/"""
    qs = Course.objects.filter(status='published').select_related('instructor')
    serializer = CourseListSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def course_detail(request, course_id):
    """GET /api/v1/lma/courses/{id}/"""
    try:
        course = Course.objects.prefetch_related(
            'modules', 'modules__lessons'
        ).get(id=course_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found.'}, status=404)
    return Response(CourseDetailSerializer(course, context={'request': request}).data)


# ── Enrollment & Payment ────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enroll(request, course_id):
    """POST /api/v1/lma/enroll/{course_id}/"""
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found.'}, status=404)

    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user, course=course
    )
    if not created:
        return Response({'message': 'Already enrolled.'}, status=200)

    course.total_students += 1
    course.save(update_fields=['total_students'])
    _send_enrollment_emails(request.user, course)
    _record_affiliate_conversion(request, course, enrollment, created)

    return Response(EnrollmentSerializer(enrollment).data, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mock_payment(request, course_id):
    """POST /api/v1/lma/mock-payment/{course_id}/"""
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found.'}, status=404)

    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user, course=course
    )
    if created:
        course.total_students += 1
        course.save(update_fields=['total_students'])
        _send_enrollment_emails(request.user, course)
        _record_affiliate_conversion(request, course, enrollment, created)

    return Response({
        'success': True,
        'message': f'Payment successful! You are now enrolled in "{course.title}".',
        'enrollment': EnrollmentSerializer(enrollment).data,
    })


# ── Student ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_dashboard(request):
    """GET /api/v1/lma/student/dashboard/"""
    user = request.user
    enrollments = Enrollment.objects.filter(student=user).select_related('course', 'course__instructor')
    certificates = Certificate.objects.filter(student=user).select_related('course')

    enrolled_course_ids = enrollments.values_list('course_id', flat=True)
    pending_assignments = Assignment.objects.filter(
        course_id__in=enrolled_course_ids,
        due_date__gte=timezone.now(),
    ).select_related('course').order_by('due_date')[:10]

    return Response({
        'name': user.get_full_name() or user.username,
        'stats': {
            'enrolled': enrollments.count(),
            'completed': enrollments.filter(completed=True).count(),
            'pending_assignments': pending_assignments.count(),
            'certificates': certificates.count(),
        },
        'enrollments': EnrollmentSerializer(enrollments, many=True).data,
        'certificates': CertificateSerializer(certificates, many=True).data,
        'pending_assignments': AssignmentSerializer(pending_assignments, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_certificates(request):
    """GET /api/v1/lma/certificates/"""
    certs = Certificate.objects.filter(student=request.user).select_related('course')
    return Response(CertificateSerializer(certs, many=True).data)


# ── Instructor dashboard ─────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_dashboard(request):
    """GET /api/v1/lma/instructor/dashboard/"""
    user = request.user
    profile = _get_or_create_lma_profile(user)

    if not profile.can_access_instructor:
        return Response({'error': 'Instructor access required.'}, status=403)

    is_super_user = _is_super(profile)
    courses = (
        Course.objects.all() if is_super_user
        else Course.objects.filter(instructor=user)
    ).order_by('-created_at')

    course_ids = courses.values_list('id', flat=True)
    pending_submissions_qs = Submission.objects.filter(
        assignment__course_id__in=course_ids,
        grade__isnull=True,
    ).select_related('assignment', 'student')
    pending_submissions = pending_submissions_qs.order_by('-submitted_at')[:20]

    total_students = sum(c.total_students for c in courses)

    stats = {
        'total_courses': courses.count(),
        'total_students': total_students,
        'pending_reviews': courses.filter(status='pending_review').count(),
        'assignments_to_grade': pending_submissions_qs.count(),
    }
    if is_super_user:
        total_revenue = sum(float(c.price) * c.total_students for c in courses)
        stats['total_earnings'] = round(total_revenue, 2)

    # Recent activity feed — enrollments, reviews, and assignment submissions
    # across this instructor's own courses, each capped at 8 and merged/sorted
    # client-side (each carries its own timestamp for that).
    recent_enrollments = (
        Enrollment.objects.filter(course_id__in=course_ids)
        .select_related('student', 'course').order_by('-enrolled_at')[:8]
    )
    recent_reviews = (
        Review.objects.filter(course_id__in=course_ids)
        .select_related('student', 'course').order_by('-created_at')[:8]
    )
    recent_submissions = (
        Submission.objects.filter(assignment__course_id__in=course_ids)
        .select_related('assignment__course', 'student').order_by('-submitted_at')[:8]
    )

    return Response({
        'name': user.get_full_name() or user.username,
        'instructor_level': profile.instructor_level,
        'stats': stats,
        'courses': CourseListSerializer(courses, many=True).data,
        'pending_submissions': SubmissionSerializer(pending_submissions, many=True).data,
        'recent_enrollments': [{
            'id': e.id,
            'student_name': e.student.get_full_name() or e.student.username,
            'course_title': e.course.title,
            'at': e.enrolled_at.isoformat(),
        } for e in recent_enrollments],
        'recent_reviews': [{
            'id': r.id,
            'student_name': r.student.get_full_name() or r.student.username,
            'course_title': r.course.title,
            'rating': r.rating,
            'at': r.created_at.isoformat(),
        } for r in recent_reviews],
        'recent_submissions': [{
            'id': s.id,
            'student_name': s.student.get_full_name() or s.student.username,
            'course_title': s.assignment.course.title,
            'assignment_title': s.assignment.title,
            'at': s.submitted_at.isoformat(),
        } for s in recent_submissions],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_course(request):
    """POST /api/v1/lma/courses/create/"""
    profile = _get_or_create_lma_profile(request.user)
    if not profile.can_access_instructor:
        return Response({'error': 'Instructor access required.'}, status=403)

    data = request.data.copy()
    # Regular instructors can only create drafts
    if not _is_super(profile):
        data['status'] = 'draft'

    serializer = CourseCreateSerializer(data=data)
    if serializer.is_valid():
        course = serializer.save(instructor=request.user)
        _send_instructor_assigned_email(request.user, course)
        return Response(CourseListSerializer(course).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_course(request, course_id):
    """PUT /api/v1/lma/courses/{id}/update/"""
    profile = _get_or_create_lma_profile(request.user)
    is_super_user = _is_super(profile)
    try:
        qs = Course.objects.all() if is_super_user else Course.objects.filter(instructor=request.user)
        course = qs.get(id=course_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found.'}, status=404)

    data = request.data.copy()
    # Regular instructors cannot directly publish; block any status that isn't draft
    if not is_super_user:
        incoming_status = data.get('status', course.status)
        if incoming_status not in ('draft',):
            data['status'] = course.status  # preserve existing status

    serializer = CourseCreateSerializer(course, data=data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(CourseListSerializer(course).data)
    return Response(serializer.errors, status=400)


# ── Assignments ──────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_assignment(request, assignment_id):
    """POST /api/v1/lma/assignments/{id}/submit/"""
    try:
        assignment = Assignment.objects.get(id=assignment_id)
    except Assignment.DoesNotExist:
        return Response({'error': 'Assignment not found.'}, status=404)

    if not Enrollment.objects.filter(student=request.user, course=assignment.course).exists():
        return Response({'error': 'Not enrolled in this course.'}, status=403)

    submission, created = Submission.objects.get_or_create(
        assignment=assignment,
        student=request.user,
        defaults={'content': clean_text(request.data.get('content', ''))},
    )
    if not created:
        submission.content = clean_text(request.data.get('content', submission.content))
        submission.submitted_at = timezone.now()
        submission.save()

    return Response(SubmissionSerializer(submission).data, status=201 if created else 200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def enrollment_status(request, course_id):
    """GET /api/v1/lma/enrollment-status/{course_id}/"""
    enrollment = Enrollment.objects.filter(student=request.user, course_id=course_id).first()
    if not enrollment:
        return Response({'enrolled': False})
    certificate = Certificate.objects.filter(student=request.user, course_id=course_id).first()
    return Response({
        'enrolled': True,
        'progress': enrollment.progress,
        'certificate': CertificateSerializer(certificate, context={'request': request}).data if certificate else None,
    })


def _lesson_view_permission(request, lesson) -> tuple:
    """Shared access check for lesson content (video, document, player, …).
    Returns (allowed: bool, error_response: Response | None).

    Order matters: free preview is open to anyone including anonymous
    visitors; admins (is_staff/is_superuser) bypass enrollment entirely,
    on ANY course, matching "Admin can preview any lesson from any course"
    — checked before the enrollment lookup so it never needs one."""
    if lesson.is_free_preview:
        return True, None
    if not request.user.is_authenticated:
        return False, Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)
    user = request.user
    if user.is_staff or user.is_superuser:
        return True, None
    course = lesson.module.course
    # Only the course's OWN instructor bypasses enrollment here — not "any
    # instructor account" (profile.can_access_instructor), which would let
    # an unrelated instructor view another instructor's paid lesson content.
    is_owner = course.instructor_id == user.id
    is_enrolled = Enrollment.objects.filter(student=user, course=course).exists()
    if not (is_enrolled or is_owner):
        return False, Response({'error': 'Enrollment required to watch this lesson.'}, status=status.HTTP_403_FORBIDDEN)
    return True, None


@api_view(['GET'])
@permission_classes([AllowAny])
def lesson_video_url(request, lesson_id):
    """GET /api/v1/lma/lessons/{lesson_id}/video/ — legacy, video-only. Kept
    for callers still using it; new code should use lesson_player_content."""
    try:
        lesson = Lesson.objects.select_related('module__course').get(id=lesson_id)
    except Lesson.DoesNotExist:
        return Response({'error': 'Lesson not found.'}, status=status.HTTP_404_NOT_FOUND)

    allowed, err = _lesson_view_permission(request, lesson)
    if not allowed:
        return err

    video_file_url = request.build_absolute_uri(lesson.video_file.url) if lesson.video_file else None
    return Response({'video_url': lesson.video_url, 'video_file': video_file_url})


@api_view(['GET'])
@permission_classes([AllowAny])
def lesson_player_content(request, lesson_id):
    """GET /api/v1/lma/lessons/{lesson_id}/player/ — everything a student
    needs to view ONE lesson's content, regardless of content_type. File
    fields are returned as absolute URLs (request.build_absolute_uri) so the
    frontend never has to guess the backend's origin itself."""
    try:
        lesson = Lesson.objects.select_related('module__course', 'module').get(id=lesson_id)
    except Lesson.DoesNotExist:
        return Response({'error': 'Lesson not found.'}, status=status.HTTP_404_NOT_FOUND)

    allowed, err = _lesson_view_permission(request, lesson)
    if not allowed:
        return err

    course = lesson.module.course
    is_admin = request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)

    assignment_data = None
    try:
        a = lesson.lesson_assignment
        assignment_data = LessonAssignmentSerializer(a).data
    except LessonAssignment.DoesNotExist:
        pass

    return Response({
        'id': lesson.id,
        'title': lesson.title,
        'content_type': lesson.content_type,
        'duration': lesson.duration,
        'content': lesson.content,
        'is_free_preview': lesson.is_free_preview,
        'is_downloadable': lesson.is_downloadable,
        'video_url': lesson.video_url,
        'video_file': request.build_absolute_uri(lesson.video_file.url) if lesson.video_file else None,
        'document_file': request.build_absolute_uri(lesson.document_file.url) if lesson.document_file else None,
        'text_content': lesson.text_content,
        'resources': lesson.resources,
        'live_session_url': lesson.live_session_url,
        'live_session_date': lesson.live_session_date,
        'assignment': assignment_data,
        'course_id': course.id,
        'course_title': course.title,
        'is_admin_preview': is_admin,
    })


def _issue_certificate_if_complete(student, course):
    """Get-or-creates the Certificate row for a 100%-complete enrollment and
    tries to render the PDF immediately. Silently no-ops if the course has
    no (renderable) template yet — the student can retry from the
    certificates page later, once the instructor uploads one."""
    certificate, _created = Certificate.objects.get_or_create(student=student, course=course)
    if certificate.certificate_file:
        return certificate
    try:
        generate_certificate_file(certificate)
    except TemplateNotRenderable:
        pass
    return certificate


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def lesson_complete(request, lesson_id):
    """POST /api/v1/lma/lessons/{lesson_id}/complete/ marks the lesson done;
    DELETE unmarks it. Both recompute the enrollment's overall progress."""
    try:
        lesson = Lesson.objects.select_related('module__course').get(id=lesson_id)
    except Lesson.DoesNotExist:
        return Response({'error': 'Lesson not found.'}, status=404)

    course = lesson.module.course
    try:
        enrollment = Enrollment.objects.get(student=request.user, course=course)
    except Enrollment.DoesNotExist:
        return Response({'error': 'Not enrolled in this course.'}, status=403)

    if request.method == 'DELETE':
        LessonProgress.objects.filter(student=request.user, lesson=lesson).delete()
    else:
        LessonProgress.objects.get_or_create(student=request.user, lesson=lesson)

    total_lessons = Lesson.objects.filter(module__course=course).count()
    completed_count = LessonProgress.objects.filter(
        student=request.user, lesson__module__course=course
    ).count()

    was_completed = enrollment.completed
    new_progress = int((completed_count / max(total_lessons, 1)) * 100)
    enrollment.progress = new_progress
    if new_progress >= 100:
        enrollment.completed = True
        if not enrollment.completed_at:
            enrollment.completed_at = timezone.now()
        _issue_certificate_if_complete(request.user, course)
    else:
        enrollment.completed = False
    enrollment.save(update_fields=['progress', 'completed', 'completed_at'])

    if enrollment.completed and not was_completed:
        _send_completion_email(request.user, course)

    return Response({
        'completed': request.method != 'DELETE',
        'progress': new_progress,
        'course_completed': enrollment.completed,
    })


# ── Certificates ──────────────────────────────────────────────────────────────

def _get_owned_course_or_404(request, course_id):
    """Fetch a course the current user may manage (their own, or any course
    if super instructor). Returns (course, None) or (None, Response)."""
    profile = _get_or_create_lma_profile(request.user)
    qs = Course.objects.all() if _is_super(profile) else Course.objects.filter(instructor=request.user)
    try:
        return qs.get(id=course_id), None
    except Course.DoesNotExist:
        return None, Response({'error': 'Course not found.'}, status=404)


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_course_certificate_template(request, course_id):
    """POST /api/v1/lma/courses/{id}/upload-certificate-template/ — instructor
    (course owner or super instructor) only. DELETE removes the template."""
    course, err = _get_owned_course_or_404(request, course_id)
    if err:
        return err
    if request.method == 'DELETE':
        course.certificate_template.delete(save=False)
        course.certificate_template = None
        course.save(update_fields=['certificate_template'])
        return Response({'certificate_template': None})
    template_file = request.FILES.get('certificate_template')
    if not template_file:
        return Response({'error': 'No certificate_template provided.'}, status=400)
    allowed_exts = ('.pdf', '.png', '.jpg', '.jpeg')
    if not template_file.name.lower().endswith(allowed_exts):
        return Response({'error': 'Certificate template must be a PDF, PNG, or JPG file.'}, status=400)
    course.certificate_template = template_file
    course.save(update_fields=['certificate_template'])
    url = request.build_absolute_uri(course.certificate_template.url)
    return Response({'certificate_template': url})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_course_certificate_template(request, course_id):
    """GET /api/v1/lma/courses/{id}/certificate-template/ — instructor only."""
    course, err = _get_owned_course_or_404(request, course_id)
    if err:
        return err
    if not course.certificate_template:
        return Response({'certificate_template': None})
    url = request.build_absolute_uri(course.certificate_template.url)
    return Response({'certificate_template': url})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_certificate(request, course_id):
    """POST /api/v1/lma/courses/{id}/generate-certificate/ — the enrolled
    student generates (or re-fetches) their certificate. Requires every
    lesson in the course to be completed and a renderable template."""
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found.'}, status=404)

    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        return Response({'error': 'Not enrolled in this course.'}, status=403)

    total_lessons = Lesson.objects.filter(module__course=course).count()
    completed_count = LessonProgress.objects.filter(
        student=request.user, lesson__module__course=course
    ).count()
    if total_lessons == 0 or completed_count < total_lessons:
        return Response({'error': 'Complete all lessons to earn your certificate.'}, status=400)

    certificate, _created = Certificate.objects.get_or_create(student=request.user, course=course)
    if not certificate.certificate_file:
        try:
            generate_certificate_file(certificate)
        except TemplateNotRenderable as exc:
            return Response({'error': str(exc)}, status=400)

    return Response(CertificateSerializer(certificate, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_certificate(request, certificate_id):
    """GET /api/v1/lma/certificates/{id}/download/ — the owning student only."""
    try:
        certificate = Certificate.objects.select_related('course', 'student').get(id=certificate_id)
    except Certificate.DoesNotExist:
        return Response({'error': 'Certificate not found.'}, status=404)
    if certificate.student_id != request.user.id and not (request.user.is_staff or request.user.is_superuser):
        return Response({'error': 'Not authorized to download this certificate.'}, status=403)
    if not certificate.certificate_file:
        return Response({'error': 'Certificate has not been generated yet.'}, status=404)
    filename = f"XERXEZ-Certificate-{certificate.course.title}.pdf"
    return FileResponse(
        certificate.certificate_file.open('rb'),
        as_attachment=True,
        filename=filename,
        content_type='application/pdf',
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_courses(request):
    """GET /api/v1/lma/student/my-courses/"""
    enrollments = (
        Enrollment.objects.filter(student=request.user)
        .select_related('course', 'course__instructor')
        .order_by('-enrolled_at')
    )
    return Response(EnrollmentSerializer(enrollments, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_assignments(request):
    """GET /api/v1/lma/student/assignments/"""
    enrolled_ids = (
        Enrollment.objects.filter(student=request.user)
        .values_list('course_id', flat=True)
    )
    assignments = (
        Assignment.objects.filter(course_id__in=enrolled_ids)
        .select_related('course')
        .order_by('due_date')
    )
    submission_map = {
        s.assignment_id: s
        for s in Submission.objects.filter(
            student=request.user,
            assignment__in=assignments,
        )
    }
    now = timezone.now()
    data = []
    for a in assignments:
        sub = submission_map.get(a.id)
        data.append({
            'id': a.id,
            'title': a.title,
            'description': a.description,
            'course_title': a.course.title,
            'course_id': a.course_id,
            'due_date': a.due_date.isoformat(),
            'submitted': sub is not None,
            'submission_id': sub.id if sub else None,
            'grade': sub.grade if sub else None,
            'overdue': (sub is None) and (a.due_date < now),
        })
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_progress(request):
    """GET /api/v1/lma/student/progress/"""
    from django.db.models import Avg, Count
    from django.db.models.functions import TruncDate
    from datetime import timedelta

    user = request.user
    enrollments = Enrollment.objects.filter(student=user).select_related('course')
    total = enrollments.count()
    completed = enrollments.filter(completed=True).count()
    agg = enrollments.aggregate(avg=Avg('progress'))
    avg_progress = int(agg['avg'] or 0)
    certificates = Certificate.objects.filter(student=user).count()

    courses_data = [
        {
            'course_id': e.course_id,
            'course_title': e.course.title,
            'progress': e.progress,
            'completed': e.completed,
            'enrolled_at': e.enrolled_at.isoformat(),
        }
        for e in enrollments.order_by('-enrolled_at')
    ]

    thirty_ago = timezone.now() - timedelta(days=30)
    daily = (
        LessonProgress.objects
        .filter(student=user, completed_at__gte=thirty_ago)
        .annotate(date=TruncDate('completed_at'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    timeline = [{'date': str(r['date']), 'lessons': r['count']} for r in daily]

    return Response({
        'stats': {
            'total_courses': total,
            'completed_courses': completed,
            'avg_progress': avg_progress,
            'certificates': certificates,
        },
        'courses': courses_data,
        'timeline': timeline,
    })


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def lma_profile(request):
    """GET /api/v1/lma/profile/ — fetch; PUT — update."""
    user = request.user
    profile = _get_or_create_lma_profile(user)

    if request.method == 'GET':
        return Response({
            'name': user.get_full_name() or user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': getattr(user, 'phone', ''),
            'username': user.username,
            'role': profile.lma_role,
            'date_joined': user.date_joined.isoformat(),
            'bio': profile.bio,
            # Was missing before — LMAStudentLayout's "Instructor Portal" switch
            # link checks exactly this field from this exact endpoint, so its
            # absence meant that link could never show, even for instructors.
            'can_access_instructor': profile.can_access_instructor,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        })

    name = clean_text(request.data.get('name', '').strip())
    email = request.data.get('email', '').strip().lower()
    phone = clean_text(request.data.get('phone', '').strip())
    bio = clean_text(request.data.get('bio', '').strip())

    if name:
        parts = name.split(' ', 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''

    if email and email != user.email:
        if User.objects.filter(email=email).exclude(pk=user.pk).exists():
            return Response({'error': 'Email already in use.'}, status=400)
        user.email = email

    if hasattr(user, 'phone'):
        user.phone = phone

    user.save()
    profile.bio = bio
    profile.save()

    return Response({'success': True, 'name': user.get_full_name() or user.username})


# ── LMA-wide admin views (is_staff / is_superuser only) ──────────────────────
# Cross-instructor visibility — a regular instructor's can_access_instructor
# check is NOT enough here, see IsLMAAdmin above.

@api_view(['GET'])
@permission_classes([IsLMAAdmin])
def admin_students(request):
    """GET /api/v1/lma/admin/students/ — every student with at least one
    enrollment, one row per student, aggregated across all their courses."""
    enrollments = Enrollment.objects.select_related('student', 'course', 'course__instructor')

    by_student = {}
    for e in enrollments:
        s = e.student
        row = by_student.setdefault(s.id, {
            'student_id': s.id,
            'student_name': s.get_full_name() or s.username,
            'email': s.email,
            'course_titles': [],
            'course_ids': [],
            'instructor_names': set(),
            'progresses': [],
            'enrolled_at': None,
            'all_completed': True,
        })
        row['course_titles'].append(e.course.title)
        row['course_ids'].append(e.course_id)
        if e.course.instructor:
            row['instructor_names'].add(e.course.instructor.get_full_name() or e.course.instructor.username)
        row['progresses'].append(e.progress)
        if row['enrolled_at'] is None or e.enrolled_at < row['enrolled_at']:
            row['enrolled_at'] = e.enrolled_at
        if not e.completed:
            row['all_completed'] = False

    results = []
    for row in by_student.values():
        progresses = row['progresses']
        avg_progress = round(sum(progresses) / len(progresses), 1) if progresses else 0
        results.append({
            'student_id': row['student_id'],
            'student_name': row['student_name'],
            'email': row['email'],
            'enrolled_courses': row['course_titles'],
            'course_ids': row['course_ids'],
            'instructor_names': sorted(row['instructor_names']),
            'progress': avg_progress,
            'enrolled_at': row['enrolled_at'].isoformat() if row['enrolled_at'] else None,
            'status': 'completed' if row['all_completed'] else 'active',
        })
    results.sort(key=lambda r: r['student_name'].lower())
    return Response(results)


@api_view(['GET'])
@permission_classes([IsLMAAdmin])
def admin_enrollments(request):
    """GET /api/v1/lma/admin/enrollments/ — flat list, one row per enrollment
    (unlike admin_students, which aggregates a student's rows together)."""
    enrollments = Enrollment.objects.select_related(
        'student', 'course', 'course__instructor'
    ).order_by('-enrolled_at')

    results = [{
        'id': e.id,
        'student_name': e.student.get_full_name() or e.student.username,
        'student_email': e.student.email,
        'course_title': e.course.title,
        'course_id': e.course_id,
        'instructor_name': (e.course.instructor.get_full_name() or e.course.instructor.username) if e.course.instructor else '—',
        'progress': e.progress,
        'enrolled_at': e.enrolled_at.isoformat(),
        'completed': e.completed,
    } for e in enrollments]
    return Response(results)


@api_view(['GET'])
@permission_classes([IsLMAAdmin])
def admin_course_analytics(request):
    """GET /api/v1/lma/admin/analytics/ — per-course enrollments, completion
    rate and revenue across every course, for the ADMIN "Course Analytics"
    page. Revenue is gross (price × enrollments), not the instructor's 70%
    cut used on the instructor Earnings page — this is platform-wide."""
    courses = Course.objects.select_related('instructor').annotate(
        enrollment_count=Count('enrollments'),
        completed_count=Count('enrollments', filter=Q(enrollments__completed=True)),
    ).order_by('-enrollment_count')

    results = [{
        'id': c.id,
        'title': c.title,
        'instructor_name': (c.instructor.get_full_name() or c.instructor.username) if c.instructor else 'Unassigned',
        'status': c.status,
        'enrollments': c.enrollment_count,
        'completion_rate': round(100 * c.completed_count / c.enrollment_count, 1) if c.enrollment_count else 0,
        'price': float(c.price),
        'revenue': round(float(c.price) * c.enrollment_count, 2),
    } for c in courses]

    totals = {
        'total_courses': len(results),
        'total_enrollments': sum(r['enrollments'] for r in results),
        'total_revenue': round(sum(r['revenue'] for r in results), 2),
        'avg_completion_rate': round(sum(r['completion_rate'] for r in results) / len(results), 1) if results else 0,
    }
    return Response({'courses': results, 'totals': totals})


# ── Admin: all LMA users (not just enrolled) — full CRUD ─────────────────────
# "Role" here is a single simplified label the admin UI edits — it's derived
# from three underlying fields (is_staff, can_access_instructor, lma_role)
# rather than being its own column, so _user_role/_apply_role are the one
# place that mapping is defined, in both directions.

def _user_role(user, profile):
    if user.is_staff or user.is_superuser:
        return 'admin'
    if profile and profile.can_access_instructor:
        return 'instructor'
    return 'student'


def _apply_role(user, profile, role):
    if role == 'admin':
        user.is_staff = True
        profile.can_access_instructor = True
        profile.lma_role = 'both'
    elif role == 'instructor':
        user.is_staff = False
        profile.can_access_instructor = True
        profile.lma_role = 'instructor'
    elif role == 'student':
        user.is_staff = False
        profile.can_access_instructor = False
        profile.lma_role = 'student'
    else:
        raise ValueError('Invalid role — must be student, instructor or admin.')


@api_view(['GET'])
@permission_classes([IsLMAAdmin])
def admin_users(request):
    """GET /api/v1/lma/admin/users/ — every registered user, including
    students with zero enrollments (unlike admin_students, which only lists
    students who have enrolled in something).

    ?role=student narrows this to the "All Students" page's definition of
    student, which is NOT simply "not staff":
      - EXCLUDES is_superuser=True (real Django/site superadmins)
      - EXCLUDES instructors (profile.can_access_instructor=True)
      - INCLUDES is_staff=True accounts that are students otherwise — these
        are "student dashboard admins" (is_staff for LMA-admin purposes),
        a different concept from a site superuser, and the page is meant to
        show them.
    """
    role_filter = request.GET.get('role')
    users = User.objects.select_related('lma_profile').all().order_by('-date_joined')
    enrollment_counts = dict(
        Enrollment.objects.values_list('student_id').annotate(c=Count('id'))
    )
    results = []
    for u in users:
        profile = getattr(u, 'lma_profile', None)
        is_instructor = bool(profile and profile.can_access_instructor)

        if role_filter == 'student' and (u.is_superuser or is_instructor):
            continue

        results.append({
            'id': u.id,
            'name': u.get_full_name() or u.username,
            'email': u.email,
            'role': 'student' if role_filter == 'student' else _user_role(u, profile),
            'is_staff': u.is_staff,
            'courses_enrolled': enrollment_counts.get(u.id, 0),
            'join_date': u.date_joined.isoformat(),
            'status': 'active' if u.is_active else 'inactive',
        })
    return Response(results)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsLMAAdmin])
def admin_user_detail(request, user_id):
    """PUT /api/v1/lma/admin/users/{id}/ — update name/email/role.
    DELETE /api/v1/lma/admin/users/{id}/ — delete the account."""
    if request.method == 'DELETE':
        if request.user.id == user_id:
            return Response({'error': 'You cannot delete your own account.'}, status=400)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=404)
        user.delete()
        return Response({'success': True})

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=404)

    profile = _get_or_create_lma_profile(user)

    name = request.data.get('name')
    email = request.data.get('email')
    account_type = request.data.get('account_type')

    if name is not None:
        name = clean_text(name.strip())
        parts = name.split(' ', 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''

    if email is not None:
        email = email.strip().lower()
        if email and User.objects.filter(email=email).exclude(pk=user.pk).exists():
            return Response({'error': 'Email already in use.'}, status=400)
        if email:
            user.email = email

    # Same two-option model as admin_create_user: this endpoint is used by
    # the "All Students" Edit modal, which only ever offers Student / Student
    # Admin — never Instructor or (site-superuser) Admin. is_superuser is
    # never touched here either way.
    if account_type is not None:
        if account_type not in ('student', 'student_admin'):
            return Response({'error': 'Invalid account type.'}, status=400)
        try:
            _apply_role(user, profile, 'student')
        except ValueError as exc:
            return Response({'error': str(exc)}, status=400)
        user.is_staff = (account_type == 'student_admin')

    user.save()
    profile.save()
    return Response({
        'id': user.id,
        'name': user.get_full_name() or user.username,
        'email': user.email,
        'role': 'student',
        'is_staff': user.is_staff,
    })


@api_view(['POST'])
@permission_classes([IsLMAAdmin])
def admin_create_user(request):
    """POST /api/v1/lma/admin/users/create/ — {name, email, password, account_type}.
    Student-only, always — the Create Account modal only ever creates
    accounts for the student dashboard. `role` is hardcoded to 'student'
    (never trusted from the request body), and `is_superuser` is never set —
    this endpoint can never grant instructor, site-superuser, ERP, or Partner
    Portal access, no matter what a client sends.

    `account_type` is the one real choice this endpoint exposes:
      - 'student'       -> is_staff=False (regular student)
      - 'student_admin' -> is_staff=True  (admin of the student dashboard
                            only — distinct from is_superuser, which this
                            endpoint can never set)
    """
    name = (request.data.get('name') or '').strip()
    email = (request.data.get('email') or '').strip().lower()
    password = request.data.get('password') or ''
    account_type = request.data.get('account_type') or 'student'
    if account_type not in ('student', 'student_admin'):
        return Response({'error': 'Invalid account type.'}, status=400)
    role = 'student'

    if not name or not email or not password:
        return Response({'error': 'Name, email and password are required.'}, status=400)
    if len(password) < 6:
        return Response({'error': 'Password must be at least 6 characters.'}, status=400)
    if not _re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return Response({'error': 'Enter a valid email address.'}, status=400)
    if User.objects.filter(email=email).exists():
        return Response({'error': 'An account with this email already exists.'}, status=400)

    base = _re.sub(r'[^a-z0-9_]', '', email.split('@')[0]) or 'user'
    username, n = base, 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{n}"; n += 1

    parts = name.split(' ', 1)
    try:
        with transaction.atomic():
            user = User(
                username=username, email=email,
                first_name=parts[0], last_name=parts[1] if len(parts) > 1 else '',
                is_active=True,
            )
            user.set_password(password)
            user._skip_profile_signal = True
            user.save()

            profile, _ = LMAProfile.objects.get_or_create(user=user)
            try:
                _apply_role(user, profile, role)
            except ValueError as exc:
                user.delete()
                return Response({'error': str(exc)}, status=400)
            # _apply_role('student') sets is_staff=False — override for the
            # student_admin case. is_superuser is never touched either way.
            user.is_staff = (account_type == 'student_admin')
            user.save()
            profile.save()
    except Exception as exc:
        return Response({'error': f'Could not create account: {exc}'}, status=400)

    return Response({
        'id': user.id,
        'name': user.get_full_name() or user.username,
        'email': user.email,
        'role': 'student',
        'is_staff': user.is_staff,
        'courses_enrolled': 0,
        'join_date': user.date_joined.isoformat(),
        'status': 'active',
    }, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """POST /api/v1/lma/profile/change-password/"""
    current = request.data.get('current_password', '')
    new_pw = request.data.get('new_password', '')

    if not current or not new_pw:
        return Response({'error': 'Both current and new password are required.'}, status=400)
    if not request.user.check_password(current):
        return Response({'error': 'Current password is incorrect.'}, status=400)
    if len(new_pw) < 6:
        return Response({'error': 'New password must be at least 6 characters.'}, status=400)

    request.user.set_password(new_pw)
    request.user.save()
    return Response({'success': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def browse_courses(request):
    """GET /api/v1/lma/courses/browse/"""
    enrolled_ids = Enrollment.objects.filter(student=request.user).values_list('course_id', flat=True)
    qs = Course.objects.filter(status='published').exclude(id__in=enrolled_ids).select_related('instructor')
    return Response(CourseListSerializer(qs, many=True).data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def grade_submission(request, submission_id):
    """PUT /api/v1/lma/submissions/{id}/grade/"""
    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        return Response({'error': 'Submission not found.'}, status=404)

    if submission.assignment.course.instructor != request.user:
        return Response({'error': 'Permission denied.'}, status=403)

    submission.grade = request.data.get('grade', submission.grade)
    submission.feedback = request.data.get('feedback', submission.feedback)
    submission.graded_at = timezone.now()
    submission.save()

    return Response(SubmissionSerializer(submission).data)


# ── Instructor — courses CRUD ────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_courses(request):
    """GET /api/v1/lma/instructor/courses/"""
    profile = _get_or_create_lma_profile(request.user)
    if not profile.can_access_instructor:
        return Response({'error': 'Instructor access required.'}, status=403)
    courses = (
        Course.objects.all() if _is_super(profile)
        else Course.objects.filter(instructor=request.user)
    ).order_by('-created_at')
    return Response(CourseListSerializer(courses, many=True).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_course(request, course_id):
    """DELETE /api/v1/lma/courses/{id}/delete/ — super instructors only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_super(profile):
        return Response({'error': 'Only super instructors can delete courses.'}, status=403)

    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found.'}, status=404)

    enrolled_count = Enrollment.objects.filter(course=course).count()
    if enrolled_count > 0:
        return Response(
            {'error': f'Cannot delete — {enrolled_count} student{"s" if enrolled_count != 1 else ""} enrolled.'},
            status=400,
        )
    course.delete()
    return Response({'success': True})


# ── Instructor — module CRUD ─────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def course_modules(request, course_id):
    """GET/POST /api/v1/lma/courses/{id}/modules/"""
    profile = _get_or_create_lma_profile(request.user)
    try:
        qs = Course.objects.all() if _is_super(profile) else Course.objects.filter(instructor=request.user)
        course = qs.get(id=course_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found.'}, status=404)

    if request.method == 'GET':
        modules = Module.objects.filter(course=course).prefetch_related('lessons').order_by('order')
        return Response(ModuleSerializer(modules, many=True, context={'request': request}).data)

    serializer = ModuleWriteSerializer(data=request.data)
    if serializer.is_valid():
        module = serializer.save(course=course)
        return Response(ModuleSerializer(module, context={'request': request}).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def module_detail_view(request, module_id):
    """PUT/DELETE /api/v1/lma/modules/{id}/"""
    profile = _get_or_create_lma_profile(request.user)
    try:
        qs = Module.objects.select_related('course').all()
        if not _is_super(profile):
            qs = qs.filter(course__instructor=request.user)
        module = qs.get(id=module_id)
    except Module.DoesNotExist:
        return Response({'error': 'Module not found.'}, status=404)

    if request.method == 'DELETE':
        module.delete()
        return Response({'success': True})

    serializer = ModuleWriteSerializer(module, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(ModuleSerializer(module, context={'request': request}).data)
    return Response(serializer.errors, status=400)


# ── Instructor — lesson CRUD ─────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def module_lessons(request, module_id):
    """GET/POST /api/v1/lma/modules/{id}/lessons/"""
    profile = _get_or_create_lma_profile(request.user)
    try:
        qs = Module.objects.select_related('course').all()
        if not _is_super(profile):
            qs = qs.filter(course__instructor=request.user)
        module = qs.get(id=module_id)
    except Module.DoesNotExist:
        return Response({'error': 'Module not found.'}, status=404)

    if request.method == 'GET':
        lessons = Lesson.objects.filter(module=module).order_by('order')
        return Response(LessonDetailSerializer(lessons, many=True, context={'request': request}).data)

    serializer = LessonWriteSerializer(data=request.data)
    if serializer.is_valid():
        lesson = serializer.save(module=module)
        return Response(LessonDetailSerializer(lesson, context={'request': request}).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def lesson_detail_view(request, lesson_id):
    """GET/PUT/DELETE /api/v1/lma/lessons/{id}/"""
    profile = _get_or_create_lma_profile(request.user)
    try:
        qs = Lesson.objects.select_related('module__course').all()
        if not _is_super(profile):
            qs = qs.filter(module__course__instructor=request.user)
        lesson = qs.get(id=lesson_id)
    except Lesson.DoesNotExist:
        return Response({'error': 'Lesson not found.'}, status=404)

    if request.method == 'GET':
        return Response(LessonDetailSerializer(lesson, context={'request': request}).data)

    if request.method == 'DELETE':
        lesson.delete()
        return Response({'success': True})

    serializer = LessonWriteSerializer(lesson, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(LessonDetailSerializer(lesson, context={'request': request}).data)
    return Response(serializer.errors, status=400)


def _get_owned_lesson_or_404(request, lesson_id):
    """Fetch a lesson the current user is allowed to edit (their own course,
    or any course if super instructor). Returns (lesson, None) or (None, Response)."""
    profile = _get_or_create_lma_profile(request.user)
    qs = Lesson.objects.select_related('module__course').all()
    if not _is_super(profile):
        qs = qs.filter(module__course__instructor=request.user)
    try:
        return qs.get(id=lesson_id), None
    except Lesson.DoesNotExist:
        return None, Response({'error': 'Lesson not found.'}, status=404)


def _student_can_view_lesson(user, lesson) -> bool:
    """A student can access lesson content (quiz, assignment, video) if the
    lesson is a free preview, they're enrolled in its course, or they're the
    course's own instructor (or staff/superuser) — same bypass rule as
    _lesson_view_permission, kept consistent across every content endpoint."""
    if lesson.is_free_preview:
        return True
    if user.is_authenticated and (user.is_staff or user.is_superuser or lesson.module.course.instructor_id == user.id):
        return True
    return Enrollment.objects.filter(student=user, course=lesson.module.course).exists()


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_lesson_video(request, lesson_id):
    """POST /api/v1/lma/lessons/{id}/upload-video/ — instructor only.
    DELETE removes the uploaded file (and clears the field) so an instructor
    can replace or drop a video without re-saving the whole lesson."""
    lesson, err = _get_owned_lesson_or_404(request, lesson_id)
    if err:
        return err
    if request.method == 'DELETE':
        lesson.video_file.delete(save=False)
        lesson.video_file = None
        lesson.save(update_fields=['video_file'])
        return Response(LessonDetailSerializer(lesson, context={'request': request}).data)
    video_file = request.FILES.get('video_file')
    if not video_file:
        return Response({'error': 'No video_file provided.'}, status=400)
    lesson.video_file = video_file
    lesson.save(update_fields=['video_file'])
    return Response(LessonDetailSerializer(lesson, context={'request': request}).data)


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_lesson_document(request, lesson_id):
    """POST /api/v1/lma/lessons/{id}/upload-document/ — instructor only.
    DELETE removes the uploaded file, same as upload_lesson_video."""
    lesson, err = _get_owned_lesson_or_404(request, lesson_id)
    if err:
        return err
    if request.method == 'DELETE':
        lesson.document_file.delete(save=False)
        lesson.document_file = None
        lesson.save(update_fields=['document_file'])
        return Response(LessonDetailSerializer(lesson, context={'request': request}).data)
    document_file = request.FILES.get('document_file')
    if not document_file:
        return Response({'error': 'No document_file provided.'}, status=400)
    lesson.document_file = document_file
    lesson.save(update_fields=['document_file'])
    return Response(LessonDetailSerializer(lesson, context={'request': request}).data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def lesson_quiz(request, lesson_id):
    """GET/POST /api/v1/lma/lessons/{id}/quiz/

    GET: instructor (owns the lesson) sees full question data including
    correct answers; a student who can view the lesson sees the quiz with
    answers withheld. POST: instructor only — creates or fully replaces the
    quiz and its question set from `{passing_score, questions: [...]}`.
    """
    try:
        lesson = Lesson.objects.select_related('module__course').get(id=lesson_id)
    except Lesson.DoesNotExist:
        return Response({'error': 'Lesson not found.'}, status=404)

    is_owner = lesson.module.course.instructor_id == request.user.id
    profile = _get_or_create_lma_profile(request.user)
    is_owner = is_owner or _is_super(profile)

    if request.method == 'GET':
        try:
            quiz = lesson.quiz
        except Quiz.DoesNotExist:
            return Response({'error': 'This lesson has no quiz yet.'}, status=404)
        if is_owner:
            return Response(QuizSerializer(quiz).data)
        if not _student_can_view_lesson(request.user, lesson):
            return Response({'error': 'Not enrolled in this course.'}, status=403)
        return Response(QuizStudentSerializer(quiz).data)

    if not is_owner:
        return Response({'error': 'Instructor access required.'}, status=403)

    passing_score = request.data.get('passing_score', 70)
    questions = request.data.get('questions', [])
    # Questions are optional — an instructor can save a quiz shell now and add
    # questions later via a repeat POST here (this endpoint fully replaces the
    # question set each call, so re-posting the existing ones plus new ones
    # is how "add more later" works).

    with transaction.atomic():
        quiz, _created = Quiz.objects.update_or_create(
            lesson=lesson, defaults={'passing_score': passing_score},
        )
        quiz.questions.all().delete()
        for i, q in enumerate(questions):
            qs = QuizQuestionSerializer(data={**q, 'order': q.get('order', i)})
            if not qs.is_valid():
                transaction.set_rollback(True)
                return Response(qs.errors, status=400)
            qs.save(quiz=quiz)

    lesson.content_type = 'quiz'
    lesson.save(update_fields=['content_type'])
    return Response(QuizSerializer(quiz).data, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_quiz(request, lesson_id):
    """POST /api/v1/lma/lessons/{id}/quiz/submit/ — student submits answers.

    Body: {"answers": {"<question_id>": "a"|"b"|"c"|"d", ...}}
    """
    try:
        lesson = Lesson.objects.select_related('module__course').get(id=lesson_id)
    except Lesson.DoesNotExist:
        return Response({'error': 'Lesson not found.'}, status=404)
    if not _student_can_view_lesson(request.user, lesson):
        return Response({'error': 'Not enrolled in this course.'}, status=403)
    try:
        quiz = lesson.quiz
    except Quiz.DoesNotExist:
        return Response({'error': 'This lesson has no quiz.'}, status=404)

    answers = request.data.get('answers', {})
    if not isinstance(answers, dict):
        return Response({'error': 'answers must be an object of {question_id: letter}.'}, status=400)

    questions = list(quiz.questions.all())
    correct = sum(
        1 for q in questions
        if str(answers.get(str(q.id), '')).lower() == q.correct_answer
    )
    score = round(100 * correct / len(questions)) if questions else 0
    passed = score >= quiz.passing_score

    attempt = QuizAttempt.objects.create(
        quiz=quiz, student=request.user, answers=answers, score=score, passed=passed,
    )
    return Response(QuizAttemptSerializer(attempt).data, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def lesson_assignment(request, lesson_id):
    """POST /api/v1/lma/lessons/{id}/assignment/ — instructor only.
    Creates or updates the lesson's assignment."""
    lesson, err = _get_owned_lesson_or_404(request, lesson_id)
    if err:
        return err

    try:
        existing = lesson.lesson_assignment
    except LessonAssignment.DoesNotExist:
        existing = None

    serializer = LessonAssignmentSerializer(existing, data=request.data, partial=bool(existing))
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    assignment = serializer.save(lesson=lesson)

    lesson.content_type = 'assignment'
    lesson.save(update_fields=['content_type'])
    return Response(LessonAssignmentSerializer(assignment).data, status=201 if not existing else 200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def submit_lesson_assignment(request, assignment_id):
    """POST /api/v1/lma/lesson-assignments/{id}/submit/ — student submits
    text/url/code content or a file, depending on the assignment's
    submission_type. Renamed from the spec's /assignments/{id}/submit/ path
    to avoid colliding with the existing course-level Assignment/Submission
    endpoint at that exact path."""
    try:
        assignment = LessonAssignment.objects.select_related('lesson__module__course').get(id=assignment_id)
    except LessonAssignment.DoesNotExist:
        return Response({'error': 'Assignment not found.'}, status=404)
    if not _student_can_view_lesson(request.user, assignment.lesson):
        return Response({'error': 'Not enrolled in this course.'}, status=403)

    content = clean_text(request.data.get('content', '').strip())
    file = request.FILES.get('file')
    if assignment.submission_type == 'file' and not file:
        return Response({'error': 'A file is required for this assignment.'}, status=400)
    if assignment.submission_type != 'file' and not content:
        return Response({'error': 'Submission content is required.'}, status=400)

    submission, _created = LessonAssignmentSubmission.objects.update_or_create(
        assignment=assignment, student=request.user,
        defaults={'content': content, **({'file': file} if file else {})},
    )
    return Response(LessonAssignmentSubmissionSerializer(submission).data, status=201)


# ── Instructor — students / reviews / analytics ──────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_students(request):
    """GET /api/v1/lma/instructor/students/ — only students enrolled in
    THIS instructor's own courses, regardless of instructor tier. Unlike
    other instructor endpoints, this deliberately has no super-instructor
    bypass: an instructor's student roster is private to their own courses."""
    profile = _get_or_create_lma_profile(request.user)
    if not profile.can_access_instructor:
        return Response({'error': 'Instructor access required.'}, status=403)

    enrollments = (
        Enrollment.objects.filter(course__instructor=request.user)
        .select_related('student', 'course')
        .order_by('-enrolled_at')
    )
    data = [{
        'id': e.id,
        'student_id': e.student.id,
        'student_name': e.student.get_full_name() or e.student.username,
        'student_email': e.student.email,
        'course_id': e.course.id,
        'course_title': e.course.title,
        'enrolled_at': e.enrolled_at.isoformat(),
        'progress': e.progress,
        'completed': e.completed,
    } for e in enrollments]
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_detail(request, student_id):
    """GET /api/v1/lma/instructor/students/{student_id}/details/"""
    profile = _get_or_create_lma_profile(request.user)
    if not profile.can_access_instructor:
        return Response({'error': 'Instructor access required.'}, status=403)

    user = get_object_or_404(User, id=student_id)

    # Regular instructors can only view students enrolled in their own courses
    if not _is_super(profile):
        own_course_ids = Course.objects.filter(instructor=request.user).values_list('id', flat=True)
        if not Enrollment.objects.filter(student=user, course_id__in=own_course_ids).exists():
            return Response({'error': 'Student not found in your courses.'}, status=404)

    enrollments = (
        Enrollment.objects.filter(student=user)
        .select_related('course')
        .order_by('-enrolled_at')
    )

    enrollments_data = []
    for enr in enrollments:
        total_lessons = Lesson.objects.filter(module__course=enr.course).count()
        completed_lessons = LessonProgress.objects.filter(
            student=user, lesson__module__course=enr.course
        ).count()
        enrollments_data.append({
            'enrollment_id': enr.id,
            'course_id': enr.course.id,
            'course_title': enr.course.title,
            'enrolled_at': enr.enrolled_at.isoformat(),
            'progress': enr.progress,
            'completed': enr.completed,
            'completed_at': enr.completed_at.isoformat() if enr.completed_at else None,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
        })

    submissions = (
        Submission.objects.filter(student=user)
        .select_related('assignment', 'assignment__course')
        .order_by('-submitted_at')
    )

    submissions_data = [{
        'id': s.id,
        'assignment_title': s.assignment.title,
        'course_title': s.assignment.course.title,
        'submitted_at': s.submitted_at.isoformat(),
        'grade': s.grade,
        'feedback': s.feedback,
        'graded_at': s.graded_at.isoformat() if s.graded_at else None,
    } for s in submissions]

    activity: list[dict] = []
    for enr in enrollments:
        activity.append({
            'type': 'enrolled',
            'timestamp': enr.enrolled_at.isoformat(),
            'description': f'Enrolled in {enr.course.title}',
        })
        if enr.completed and enr.completed_at:
            activity.append({
                'type': 'completed_course',
                'timestamp': enr.completed_at.isoformat(),
                'description': f'Completed {enr.course.title}',
            })

    lesson_completions = (
        LessonProgress.objects.filter(student=user)
        .select_related('lesson__module__course')
        .order_by('-completed_at')[:20]
    )
    for lp in lesson_completions:
        activity.append({
            'type': 'completed_lesson',
            'timestamp': lp.completed_at.isoformat(),
            'description': f'Completed "{lp.lesson.title}" in {lp.lesson.module.course.title}',
        })

    for s in submissions:
        activity.append({
            'type': 'submitted_assignment',
            'timestamp': s.submitted_at.isoformat(),
            'description': f'Submitted "{s.assignment.title}" for {s.assignment.course.title}',
        })

    for cert in Certificate.objects.filter(student=user).select_related('course'):
        activity.append({
            'type': 'earned_certificate',
            'timestamp': cert.issued_at.isoformat(),
            'description': f'Earned certificate for {cert.course.title}',
        })

    activity.sort(key=lambda x: x['timestamp'], reverse=True)

    return Response({
        'id': user.id,
        'name': user.get_full_name() or user.username,
        'email': user.email,
        'username': user.username,
        'date_joined': user.date_joined.isoformat(),
        'enrollments': enrollments_data,
        'submissions': submissions_data,
        'activity': activity[:30],
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def unenroll_student(request, enrollment_id):
    """DELETE /api/v1/lma/instructor/enrollments/{enrollment_id}/"""
    profile = _get_or_create_lma_profile(request.user)
    if not profile.can_access_instructor:
        return Response({'error': 'Instructor access required.'}, status=403)

    enrollment = get_object_or_404(Enrollment, id=enrollment_id)

    # Regular instructors can only unenroll from their own courses
    if not _is_super(profile) and enrollment.course.instructor != request.user:
        return Response({'error': 'Permission denied.'}, status=403)

    course = enrollment.course
    student = enrollment.student

    LessonProgress.objects.filter(student=student, lesson__module__course=course).delete()
    enrollment.delete()

    if course.total_students > 0:
        course.total_students = max(0, course.total_students - 1)
        course.save(update_fields=['total_students'])

    return Response({'success': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_reviews(request):
    """GET /api/v1/lma/instructor/reviews/"""
    profile = _get_or_create_lma_profile(request.user)
    course_qs = (
        Course.objects.all() if _is_super(profile)
        else Course.objects.filter(instructor=request.user)
    )
    course_ids = course_qs.values_list('id', flat=True)
    reviews = (
        Review.objects.filter(course_id__in=course_ids)
        .select_related('student', 'course')
        .order_by('-created_at')
    )
    data = [{
        'id': r.id,
        'student_name': r.student.get_full_name() or r.student.username,
        'course_title': r.course.title,
        'rating': r.rating,
        'comment': r.comment,
        'created_at': r.created_at.isoformat(),
    } for r in reviews]
    return Response(data)


def _recompute_course_rating(course):
    from django.db.models import Avg, Count
    agg = Review.objects.filter(course=course).aggregate(avg=Avg('rating'), count=Count('id'))
    course.rating = round(agg['avg'] or 0, 1)
    course.total_ratings = agg['count'] or 0
    course.save(update_fields=['rating', 'total_ratings'])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_review(request, course_id):
    """POST /api/v1/lma/courses/{course_id}/review/ — enrolled students only.
    Any enrolled student may leave a review at any point (no completion gate).
    Resubmitting updates the student's existing review for the course."""
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found.'}, status=404)

    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        return Response({'error': 'You must be enrolled in this course to leave a review.'}, status=403)

    rating = request.data.get('rating')
    comment = clean_text(request.data.get('comment', '').strip())

    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return Response({'error': 'Rating is required and must be a number.'}, status=400)
    if rating < 1 or rating > 5:
        return Response({'error': 'Rating must be between 1 and 5.'}, status=400)

    review, _created = Review.objects.update_or_create(
        student=request.user, course=course,
        defaults={'rating': rating, 'comment': comment},
    )
    _recompute_course_rating(course)

    return Response({
        'id': review.id,
        'rating': review.rating,
        'comment': review.comment,
        'created_at': review.created_at.isoformat(),
        'course_rating': float(course.rating),
        'course_total_ratings': course.total_ratings,
    }, status=201 if _created else 200)


@api_view(['GET'])
@permission_classes([AllowAny])
def course_reviews(request, course_id):
    """GET /api/v1/lma/courses/{course_id}/reviews/ — public list of reviews for a course."""
    reviews = (
        Review.objects.filter(course_id=course_id)
        .select_related('student')
        .order_by('-created_at')
    )
    data = [{
        'id': r.id,
        'student_name': r.student.get_full_name() or r.student.username,
        'rating': r.rating,
        'comment': r.comment,
        'created_at': r.created_at.isoformat(),
    } for r in reviews]
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_review_for_course(request, course_id):
    """GET /api/v1/lma/courses/{course_id}/review/ — the current student's own review, if any."""
    review = Review.objects.filter(student=request.user, course_id=course_id).first()
    if not review:
        return Response(None)
    return Response({
        'id': review.id,
        'rating': review.rating,
        'comment': review.comment,
        'created_at': review.created_at.isoformat(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_analytics(request):
    """GET /api/v1/lma/instructor/analytics/"""
    from django.db.models import Avg

    profile = _get_or_create_lma_profile(request.user)
    is_super_user = _is_super(profile)
    courses = (
        Course.objects.all() if is_super_user
        else Course.objects.filter(instructor=request.user)
    ).order_by('-created_at')

    data = []
    for c in courses:
        enrollments = Enrollment.objects.filter(course=c)
        completed = enrollments.filter(completed=True).count()
        total = enrollments.count()
        avg_rating = Review.objects.filter(course=c).aggregate(avg=Avg('rating'))['avg'] or 0
        entry = {
            'id': c.id,
            'title': c.title,
            'total_students': c.total_students,
            'completed': completed,
            'completion_rate': round((completed / max(total, 1)) * 100, 1),
            'avg_rating': round(float(avg_rating), 1),
            'status': c.status,
        }
        if is_super_user:
            entry['revenue'] = round(float(c.price) * c.total_students, 2)
        data.append(entry)
    return Response(data)


# ── Instructor management (super only) ──────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_list(request):
    """GET /api/v1/lma/instructor/instructors/ — list instructor accounts only.

    Deliberately excludes superusers and any profile whose lma_role isn't
    plain 'instructor' (e.g. 'both', used by admin accounts that also teach)
    — this is the instructor-management roster, not a full user directory."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_instructor_admin(request.user, profile):
        return Response({'error': 'Instructor admin access required.'}, status=403)

    instructor_profiles = LMAProfile.objects.filter(
        can_access_instructor=True, lma_role='instructor', user__is_superuser=False
    ).select_related('user').order_by('instructor_level', 'user__date_joined')

    data = [{
        'id': p.user.id,
        'name': p.user.get_full_name() or p.user.username,
        'email': p.user.email,
        'username': p.user.username,
        'instructor_level': p.instructor_level,
        'is_staff': p.user.is_staff,
        'date_joined': p.user.date_joined.isoformat(),
        'course_count': Course.objects.filter(instructor=p.user).count(),
    } for p in instructor_profiles]
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_instructor(request):
    """POST /api/v1/lma/instructor/create-instructor/ — instructor admin only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_instructor_admin(request.user, profile):
        return Response({'error': 'Instructor admin access required.'}, status=403)

    name = request.data.get('name', '').strip()
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')
    bio = request.data.get('bio', '').strip()
    account_type = request.data.get('account_type', 'instructor')

    if not name or not email or not password:
        return Response({'error': 'Name, email and password are required.'}, status=400)
    if len(password) < 6:
        return Response({'error': 'Password must be at least 6 characters.'}, status=400)
    if not _re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return Response({'error': 'Enter a valid email address.'}, status=400)
    if User.objects.filter(email=email).exists():
        return Response({'error': 'An account with this email already exists.'}, status=400)
    if account_type not in ('instructor', 'instructor_admin'):
        return Response({'error': 'account_type must be "instructor" or "instructor_admin".'}, status=400)

    base = _re.sub(r'[^a-z0-9_]', '', email.split('@')[0]) or 'instructor'
    username, n = base, 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{n}"; n += 1

    parts = name.split(' ', 1)
    try:
        with transaction.atomic():
            user = User(
                username=username, email=email,
                first_name=parts[0], last_name=parts[1] if len(parts) > 1 else '',
                is_active=True, is_staff=(account_type == 'instructor_admin'),
            )
            user.set_password(password)
            user._skip_profile_signal = True
            user.save()

            lma_profile, _ = LMAProfile.objects.get_or_create(user=user)
            lma_profile.lma_role = 'instructor'
            lma_profile.can_access_student = False
            lma_profile.can_access_instructor = True
            lma_profile.instructor_level = 'regular'
            lma_profile.bio = bio
            lma_profile.save()
    except Exception as exc:
        return Response({'error': f'Could not create instructor: {exc}'}, status=400)

    return Response({
        'id': user.id,
        'name': name,
        'email': email,
        'username': username,
        'instructor_level': 'regular',
        'is_staff': user.is_staff,
    }, status=201)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_instructor(request, instructor_id):
    """PUT /api/v1/lma/instructor/instructors/{id}/ — instructor admin only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_instructor_admin(request.user, profile):
        return Response({'error': 'Instructor admin access required.'}, status=403)

    try:
        target_user = User.objects.get(id=instructor_id)
    except User.DoesNotExist:
        return Response({'error': 'Instructor not found.'}, status=404)

    try:
        target_profile = target_user.lma_profile
    except LMAProfile.DoesNotExist:
        return Response({'error': 'Instructor profile not found.'}, status=404)

    full_name      = request.data.get('full_name', '').strip()
    email          = request.data.get('email', '').strip().lower()
    new_level      = request.data.get('instructor_level', '').strip()
    account_type   = request.data.get('account_type', '').strip()

    # Validate level value
    if new_level and new_level not in ('regular', 'super'):
        return Response({'error': 'instructor_level must be "regular" or "super".'}, status=400)

    if account_type and account_type not in ('instructor', 'instructor_admin'):
        return Response({'error': 'account_type must be "instructor" or "instructor_admin".'}, status=400)

    # Cannot demote a super instructor
    if new_level and new_level != target_profile.instructor_level and _is_super(target_profile):
        return Response({'error': 'Cannot change a super instructor\'s level.'}, status=400)

    # Cannot change own level
    if new_level and target_user.id == request.user.id and new_level != profile.instructor_level:
        return Response({'error': 'Cannot change your own instructor level.'}, status=400)

    # Guard: don't leave zero super instructors
    if new_level == 'regular' and target_profile.instructor_level == 'super':
        super_count = LMAProfile.objects.filter(
            can_access_instructor=True, instructor_level='super'
        ).count()
        if super_count <= 1:
            return Response({'error': 'Cannot demote — this is the only super instructor.'}, status=400)

    # Email uniqueness check
    if email and email != target_user.email:
        if User.objects.filter(email=email).exclude(pk=target_user.pk).exists():
            return Response({'error': 'Email already in use by another account.'}, status=400)
        target_user.email = email

    # Update name
    if full_name:
        parts = full_name.split(' ', 1)
        target_user.first_name = parts[0]
        target_user.last_name  = parts[1] if len(parts) > 1 else ''
    if account_type:
        target_user.is_staff = (account_type == 'instructor_admin')
    target_user.save()

    # Update level
    if new_level:
        target_profile.instructor_level = new_level
        target_profile.save(update_fields=['instructor_level'])

    return Response({
        'success': True,
        'id': target_user.id,
        'name': target_user.get_full_name() or target_user.username,
        'email': target_user.email,
        'instructor_level': target_profile.instructor_level,
        'is_staff': target_user.is_staff,
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_instructor(request, instructor_id):
    """DELETE /api/v1/lma/instructor/instructors/{id}/ — instructor admin only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_instructor_admin(request.user, profile):
        return Response({'error': 'Instructor admin access required.'}, status=403)

    if int(instructor_id) == request.user.id:
        return Response({'error': 'Cannot delete your own account.'}, status=400)

    try:
        target_user = User.objects.get(id=instructor_id)
    except User.DoesNotExist:
        return Response({'error': 'Instructor not found.'}, status=404)

    try:
        target_profile = target_user.lma_profile
    except LMAProfile.DoesNotExist:
        return Response({'error': 'Instructor profile not found.'}, status=404)

    if _is_super(target_profile):
        return Response({'error': 'Cannot delete a super instructor account.'}, status=403)

    # Unassign courses before deleting user
    courses_qs = Course.objects.filter(instructor=target_user)
    courses_count = courses_qs.count()
    courses_qs.update(status='draft', instructor=None)

    with transaction.atomic():
        target_profile.delete()
        target_user.delete()

    return Response({'success': True, 'courses_unassigned': courses_count})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_course_list(request, instructor_id):
    """GET /api/v1/lma/instructor/instructors/{id}/courses/ — instructor admin only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_instructor_admin(request.user, profile):
        return Response({'error': 'Instructor admin access required.'}, status=403)

    try:
        target_user = User.objects.get(id=instructor_id)
    except User.DoesNotExist:
        return Response({'error': 'Instructor not found.'}, status=404)

    courses = Course.objects.filter(instructor=target_user).order_by('-created_at')
    data = [{
        'id': c.id,
        'title': c.title,
        'status': c.status,
        'total_students': c.total_students,
        'created_at': c.created_at.date().isoformat(),
    } for c in courses]
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_instructor_password(request, instructor_id):
    """POST /api/v1/lma/instructor/instructors/{id}/reset-password/ — instructor admin only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_instructor_admin(request.user, profile):
        return Response({'error': 'Instructor admin access required.'}, status=403)

    try:
        target_user = User.objects.get(id=instructor_id)
    except User.DoesNotExist:
        return Response({'error': 'Instructor not found.'}, status=404)

    custom_password = request.data.get('password', '').strip()

    if custom_password:
        if len(custom_password) < 6:
            return Response({'error': 'Password must be at least 6 characters.'}, status=400)
        new_password = custom_password
    else:
        import secrets as _sec
        import string as _str
        alphabet = _str.ascii_letters + _str.digits + '!@#$'
        new_password = ''.join(_sec.choice(alphabet) for _ in range(12))

    target_user.set_password(new_password)
    target_user.save(update_fields=['password'])

    full_name = target_user.get_full_name() or target_user.username
    admin_name = request.user.get_full_name() or request.user.username

    # In-app bell notification for the instructor
    Notification.objects.create(
        recipient=target_user,
        title='Your Password Has Been Reset',
        message=f'{admin_name} has reset your account password. Check your email for the new credentials.',
    )

    _send_safe(
        subject='XERXEZ Academy — Your Password Has Been Reset',
        message=(
            f'Hi {full_name},\n\n'
            f'An administrator has reset your XERXEZ Academy instructor account password.\n\n'
            f'Your new password:\n'
            f'  {new_password}\n\n'
            f'Sign in at: https://xerxez.com/lma/login\n\n'
            f'Please change your password after logging in.\n\n'
            f'— XERXEZ Academy Team'
        ),
        recipient_list=[target_user.email],
    )

    return Response({'success': True, 'email': target_user.email})


# ── Course review workflow ───────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_for_review(request, course_id):
    """POST /api/v1/lma/courses/{id}/submit-for-review/"""
    profile = _get_or_create_lma_profile(request.user)
    if not profile.can_access_instructor:
        return Response({'error': 'Instructor access required.'}, status=403)

    try:
        course = Course.objects.get(id=course_id, instructor=request.user)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found.'}, status=404)

    if course.status not in ('draft', 'rejected'):
        return Response(
            {'error': f'Cannot submit — course is currently "{course.status}".'},
            status=400,
        )

    course.status = 'pending_review'
    course.rejection_reason = ''
    course.save(update_fields=['status', 'rejection_reason'])

    instructor_name = request.user.get_full_name() or request.user.username

    # Notify super instructors in-app — use email iexact + profile as dual guard
    from django.db.models import Q as _Q
    email_q = _Q()
    for _e in SUPER_INSTRUCTOR_EMAILS:
        email_q |= _Q(email__iexact=_e)
    uname_q = _Q()
    for _u in INSTRUCTOR_USERNAMES:
        uname_q |= _Q(username__iexact=_u)
    super_users = User.objects.filter(
        email_q | uname_q |
        _Q(lma_profile__instructor_level='super', lma_profile__can_access_instructor=True)
    ).distinct()
    for su in super_users:
        Notification.objects.create(
            recipient=su,
            title='Course Submitted for Review',
            message=f'"{course.title}" by {instructor_name} is awaiting your review.',
            course=course,
        )

    # Send email to super instructors
    _send_safe(
        subject=f'[Xerxez LMA] Course Review Request: {course.title}',
        message=(
            f'Hello,\n\n'
            f'{instructor_name} has submitted the course "{course.title}" for review.\n\n'
            f'Please log in to the Xerxez LMA instructor dashboard to review and publish or reject it.\n\n'
            f'— Xerxez LMA'
        ),
        recipient_list=SUPER_INSTRUCTOR_EMAILS,
    )

    return Response({'success': True, 'status': 'pending_review'})


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def publish_course(request, course_id):
    """PUT /api/v1/lma/courses/{id}/publish/ — super instructor or LMA admin."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_lma_admin_or_super(request.user, profile):
        return Response({'error': 'Super instructor or admin access required.'}, status=403)

    try:
        course = Course.objects.select_related('instructor').get(id=course_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found.'}, status=404)

    if course.status != 'pending_review':
        return Response(
            {'error': f'Course is "{course.status}" — only pending_review courses can be published.'},
            status=400,
        )

    course.status = 'published'
    course.rejection_reason = ''
    course.save(update_fields=['status', 'rejection_reason'])

    # Notify instructor in-app — orphaned courses (instructor=None) have no one to notify
    if course.instructor:
        Notification.objects.create(
            recipient=course.instructor,
            title='Course Published!',
            message=f'Congratulations! Your course "{course.title}" has been published.',
            course=course,
        )

        # Email instructor
        if course.instructor.email:
            _send_safe(
                subject=f'[Xerxez LMA] Your course "{course.title}" is now live!',
                message=(
                    f'Hi {course.instructor.get_full_name() or course.instructor.username},\n\n'
                    f'Great news! Your course "{course.title}" has been reviewed and is now published on Xerxez LMA.\n\n'
                    f'Students can now enroll and start learning.\n\n'
                    f'— Xerxez LMA'
                ),
                recipient_list=[course.instructor.email],
            )

    return Response({'success': True, 'status': 'published'})


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def reject_course(request, course_id):
    """PUT /api/v1/lma/courses/{id}/reject/ — super instructor or LMA admin."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_lma_admin_or_super(request.user, profile):
        return Response({'error': 'Super instructor or admin access required.'}, status=403)

    try:
        course = Course.objects.select_related('instructor').get(id=course_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found.'}, status=404)

    if course.status != 'pending_review':
        return Response(
            {'error': f'Course is "{course.status}" — only pending_review courses can be rejected.'},
            status=400,
        )

    reason = request.data.get('reason', '').strip()
    if not reason:
        return Response({'error': 'A rejection reason is required.'}, status=400)

    course.status = 'rejected'
    course.rejection_reason = reason
    course.save(update_fields=['status', 'rejection_reason'])

    # Notify instructor in-app — orphaned courses (instructor=None) have no one to notify
    if course.instructor:
        Notification.objects.create(
            recipient=course.instructor,
            title='Course Needs Changes',
            message=f'Your course "{course.title}" was not approved. Reason: {reason}',
            course=course,
        )

        # Email instructor
        if course.instructor.email:
            _send_safe(
                subject=f'[Xerxez LMA] Course "{course.title}" — Changes Required',
                message=(
                    f'Hi {course.instructor.get_full_name() or course.instructor.username},\n\n'
                    f'Your course "{course.title}" requires some changes before it can be published.\n\n'
                    f'Feedback: {reason}\n\n'
                    f'Please update your course and re-submit for review.\n\n'
                    f'— Xerxez LMA'
                ),
                recipient_list=[course.instructor.email],
            )

    return Response({'success': True, 'status': 'rejected'})


# ── Notifications ────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    """GET /api/v1/lma/notifications/"""
    notifs = Notification.objects.filter(recipient=request.user)[:50]
    data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat(),
        'course_id': n.course_id,
    } for n in notifs]
    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return Response({'notifications': data, 'unread_count': unread})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notif_id):
    """POST /api/v1/lma/notifications/{id}/read/"""
    try:
        notif = Notification.objects.get(id=notif_id, recipient=request.user)
    except Notification.DoesNotExist:
        return Response({'error': 'Notification not found.'}, status=404)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return Response({'success': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """POST /api/v1/lma/notifications/read-all/"""
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return Response({'success': True})


# ── Pending review queue (super only) ───────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_review_queue(request):
    """GET /api/v1/lma/instructor/pending-reviews/"""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_lma_admin_or_super(request.user, profile):
        return Response({'error': 'Super instructor or admin access required.'}, status=403)

    courses = Course.objects.filter(
        status='pending_review'
    ).select_related('instructor').order_by('-updated_at')

    data = [{
        'id': c.id,
        'title': c.title,
        'description': c.description[:200],
        'instructor_name': (c.instructor.get_full_name() or c.instructor.username) if c.instructor else 'Unassigned',
        'instructor_email': c.instructor.email if c.instructor else '',
        'category': c.category,
        'level': c.level,
        'price': float(c.price),
        'updated_at': c.updated_at.isoformat(),
    } for c in courses]
    return Response(data)


# ── Instructor Applications ──────────────────────────────────────────────────

def _get_super_users():
    """Return all super-instructor User objects via email/username/profile."""
    from django.db.models import Q as _Q
    email_q = _Q()
    for _e in SUPER_INSTRUCTOR_EMAILS:
        email_q |= _Q(email__iexact=_e)
    uname_q = _Q()
    for _u in INSTRUCTOR_USERNAMES:
        uname_q |= _Q(username__iexact=_u)
    return User.objects.filter(
        email_q | uname_q |
        _Q(lma_profile__instructor_level='super', lma_profile__can_access_instructor=True)
    ).distinct()


EXPERTISE_CHOICES = ('AI & ML', 'DevSecOps', 'Cloud', 'Web Dev', 'Data Science', 'Business', 'Other')


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([BecomeInstructorRateThrottle])
def become_instructor(request):
    """POST /api/v1/lma/become-instructor/ — public, no auth required."""
    applicant_type = request.data.get('applicant_type', 'individual').strip()
    company_size   = clean_text(request.data.get('company_size', '').strip())
    full_name    = clean_text(request.data.get('full_name', '').strip())
    company_name = clean_text(request.data.get('company_name', '').strip())
    email        = request.data.get('email', '').strip().lower()
    phone        = clean_text(request.data.get('phone', '').strip())
    linkedin_url = request.data.get('linkedin_url', '').strip()
    website      = request.data.get('website', '').strip()
    expertise    = request.data.get('expertise', '').strip()
    years_experience = request.data.get('years_experience', 0)
    bio          = clean_text(request.data.get('bio', '').strip())
    previous_teaching_experience = bool(request.data.get('previous_teaching_experience'))
    why_teach    = clean_text(request.data.get('why_teach', '').strip())
    proposed_course_title = clean_text(request.data.get('proposed_course_title', '').strip())
    course_description     = clean_text(request.data.get('course_description', '').strip())
    target_audience         = clean_text(request.data.get('target_audience', '').strip())
    estimated_duration      = clean_text(request.data.get('estimated_duration', '').strip())
    agree_terms    = bool(request.data.get('agree_terms'))
    confirm_rights = bool(request.data.get('confirm_rights'))
    password     = request.data.get('password', '')

    required = {
        'Full name': full_name, 'Email': email, 'Phone': phone,
        'Bio': bio, 'Why teach': why_teach,
        'Proposed course title': proposed_course_title,
        'Course description': course_description,
        'Target audience': target_audience,
        'Estimated duration': estimated_duration,
    }
    if applicant_type not in ('individual', 'company'):
        return Response({'error': 'applicant_type must be "individual" or "company".'}, status=400)
    if applicant_type == 'company':
        required['Company name'] = company_name
        required['Company size'] = company_size
    missing = [label for label, value in required.items() if not value]
    if missing:
        return Response({'error': f'{", ".join(missing)} {"is" if len(missing) == 1 else "are"} required.'}, status=400)
    if not password or len(password) < 6:
        return Response({'error': 'Password must be at least 6 characters.'}, status=400)
    if not _re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return Response({'error': 'Enter a valid email address.'}, status=400)
    # `phone` arrives as "+<country code><national number>" from the frontend's
    # country-code picker — a loose 8-15 total-digit bound (E.164 max length)
    # is the right server-side check; per-country digit rules are enforced
    # client-side where the selected country is known.
    if not phone.startswith('+') or not (8 <= len(_re.sub(r'\D', '', phone)) <= 15):
        return Response({'error': 'Please enter a valid phone number.'}, status=400)
    if expertise not in EXPERTISE_CHOICES:
        return Response({'error': 'Select a valid area of expertise.'}, status=400)
    try:
        years_experience = int(years_experience)
    except (TypeError, ValueError):
        return Response({'error': 'Years of experience must be a number.'}, status=400)
    if len(bio) < 10:
        return Response({'error': 'Bio must be at least 10 characters.'}, status=400)
    if len(bio) > 500:
        return Response({'error': 'Bio must be at most 500 characters.'}, status=400)
    if len(why_teach) < 10:
        return Response({'error': 'Why-teach must be at least 10 characters.'}, status=400)
    if len(why_teach) > 500:
        return Response({'error': 'Why-teach must be at most 500 characters.'}, status=400)
    if not agree_terms or not confirm_rights:
        return Response({'error': 'You must agree to the terms and confirm content ownership.'}, status=400)

    if InstructorApplication.objects.filter(email=email).exists():
        return Response({'error': 'An application with this email already exists.'}, status=400)
    if User.objects.filter(email=email).exists():
        return Response({'error': 'This email is already registered. Please sign in.'}, status=400)

    from django.contrib.auth.hashers import make_password
    app = InstructorApplication.objects.create(
        applicant_type=applicant_type, company_size=company_size,
        full_name=full_name, company_name=company_name, email=email, phone=phone,
        linkedin_url=linkedin_url, website=website,
        expertise=expertise, years_experience=years_experience, bio=bio,
        previous_teaching_experience=previous_teaching_experience, why_teach=why_teach,
        proposed_course_title=proposed_course_title, course_description=course_description,
        target_audience=target_audience, estimated_duration=estimated_duration,
        agree_terms=agree_terms, confirm_rights=confirm_rights,
        password_hash=make_password(password),
    )

    # Notify super instructors in-app
    for su in _get_super_users():
        Notification.objects.create(
            recipient=su,
            title='New Instructor Application',
            message=f'{full_name} ({email}) has applied to become an instructor.',
        )

    # Two notification emails on submit — sent independently of each other so
    # one failing (e.g. a bad recipient address) never blocks the other, and
    # neither ever surfaces to the user: the application is already saved by
    # this point, and a broken SMTP config shouldn't turn into a 500 for the
    # applicant. Each failure is logged silently instead.
    applicant_label = company_name or full_name
    # Two notification emails on submit — sent independently of each other so
    # one failing never blocks the other, and neither ever surfaces to the
    # user or blocks the response: the application is already saved above,
    # and a broken/unconfigured email setup shouldn't turn into a 500 for
    # the applicant. _send_safe wraps send_mail in try/except and skips
    # entirely (just a warning) if EMAIL_HOST_USER isn't configured.
    _send_safe(
        subject='We received your instructor application',
        message=(
            f'Hi {full_name}, thank you for applying. '
            f"We'll review within 2-3 business days and contact you at this email."
        ),
        recipient_list=[email],
    )
    _send_safe(
        subject=f'New instructor application from {applicant_label}',
        message=(
            f'Full name: {full_name}\n'
            f'Company: {company_name or "Not specified"}\n'
            f'Email: {email}\n'
            f'Phone: {phone}\n'
            f'Expertise: {expertise or "Not specified"} ({years_experience} yrs)\n'
            f'Proposed course: {proposed_course_title}\n\n'
            f'Course description:\n{course_description}\n\n'
            f'Bio:\n{bio}\n\n'
            f'Why teach:\n{why_teach}\n\n'
            f'Review it here: https://xerxez.com/lma/instructor/dashboard'
        ),
        recipient_list=['info@xerxez.com'],
    )

    return Response({'success': True, 'application_id': app.id}, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_applications(request):
    """GET /api/v1/lma/instructor/applications/?status=pending"""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_instructor_admin(request.user, profile):
        return Response({'error': 'Instructor admin access required.'}, status=403)

    status_filter = request.query_params.get('status', '')
    qs = InstructorApplication.objects.all()
    if status_filter in ('pending', 'approved', 'rejected'):
        qs = qs.filter(status=status_filter)

    pending_count = InstructorApplication.objects.filter(status='pending').count()
    data = [{
        'id': a.id,
        'applicant_type': a.applicant_type,
        'company_size': a.company_size,
        'full_name': a.full_name,
        'company_name': a.company_name,
        'email': a.email,
        'phone': a.phone,
        'linkedin_url': a.linkedin_url,
        'website': a.website,
        'expertise': a.expertise,
        'years_experience': a.years_experience,
        'bio': a.bio,
        'previous_teaching_experience': a.previous_teaching_experience,
        'why_teach': a.why_teach,
        'proposed_course_title': a.proposed_course_title,
        'course_description': a.course_description,
        'target_audience': a.target_audience,
        'estimated_duration': a.estimated_duration,
        'status': a.status,
        'rejection_reason': a.rejection_reason,
        'applied_at': a.applied_at.isoformat(),
        'reviewed_at': a.reviewed_at.isoformat() if a.reviewed_at else None,
        'reviewed_by': a.reviewed_by.get_full_name() or a.reviewed_by.username if a.reviewed_by else None,
    } for a in qs]
    return Response({'applications': data, 'pending_count': pending_count})


def _promote_to_instructor_profile(user, app):
    """Give `user` a regular-instructor LMAProfile carrying the application's
    bio and partner-branding fields. Shared by both approval paths (new
    account and reinstated account) so they can never drift apart."""
    profile, _ = LMAProfile.objects.get_or_create(user=user)
    profile.lma_role = 'instructor'
    profile.can_access_student = False
    profile.can_access_instructor = True
    profile.instructor_level = 'regular'
    profile.bio = app.bio
    profile.company_name = app.company_name
    profile.website = app.website
    profile.linkedin_url = app.linkedin_url
    profile.save()
    return profile


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_application(request, app_id):
    """POST /api/v1/lma/instructor/applications/{id}/approve/ — instructor admin only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_instructor_admin(request.user, profile):
        return Response({'error': 'Instructor admin access required.'}, status=403)

    try:
        app = InstructorApplication.objects.get(id=app_id)
    except InstructorApplication.DoesNotExist:
        return Response({'error': 'Application not found.'}, status=404)

    import secrets
    import string

    # If the applicant chose a password at apply time, reuse its stored hash;
    # otherwise generate a temporary one to email.
    alphabet = string.ascii_letters + string.digits + '!@#$'
    raw_password = ''.join(secrets.choice(alphabet) for _ in range(14))
    use_chosen = bool(app.password_hash)
    password_line = 'the password you chose when applying' if use_chosen else raw_password

    existing_user = User.objects.filter(email=app.email).first()

    if existing_user:
        # Re-approving a previously rejected application whose account already exists —
        # re-activate the account, restore instructor profile, and send a new temp password.
        try:
            with transaction.atomic():
                existing_user.is_active = True
                if use_chosen:
                    existing_user.password = app.password_hash
                else:
                    existing_user.set_password(raw_password)
                existing_user.save(update_fields=['is_active', 'password'])

                _promote_to_instructor_profile(existing_user, app)

                app.status = 'approved'
                app.rejection_reason = ''
                app.reviewed_at = timezone.now()
                app.reviewed_by = request.user
                app.save(update_fields=['status', 'rejection_reason', 'reviewed_at', 'reviewed_by'])
        except Exception as exc:
            return Response({'error': f'Could not restore instructor account: {exc}'}, status=400)

        _send_safe(
            subject='XERXEZ Academy — Your Instructor Access Has Been Reinstated',
            message=(
                f'Hi {app.full_name},\n\n'
                f'Great news! Your instructor application has been approved and your account has been reinstated.\n\n'
                f'Your login credentials:\n'
                f'  Email: {app.email}\n'
                f'  Password: {password_line}\n\n'
                f'Sign in at: https://xerxez.com/lma/login\n\n'
                f'Please change your password after first login.\n\n'
                f'— XERXEZ Academy Team'
            ),
            recipient_list=[app.email],
        )
        return Response({
            'success': True,
            'email': app.email,
            'message': f'Account reinstated. New credentials sent to {app.email}.',
        })

    # Fresh approval — create brand-new instructor account.
    base = _re.sub(r'[^a-z0-9_]', '', app.email.split('@')[0]) or 'instructor'
    username, n = base, 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{n}"; n += 1

    parts = app.full_name.split(' ', 1)
    try:
        with transaction.atomic():
            user = User(
                username=username, email=app.email,
                first_name=parts[0], last_name=parts[1] if len(parts) > 1 else '',
                is_active=True,
            )
            if use_chosen:
                user.password = app.password_hash
            else:
                user.set_password(raw_password)
            user._skip_profile_signal = True
            user.save()

            _promote_to_instructor_profile(user, app)

            app.status = 'approved'
            app.reviewed_at = timezone.now()
            app.reviewed_by = request.user
            app.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
    except Exception as exc:
        return Response({'error': f'Could not create instructor account: {exc}'}, status=400)

    _send_safe(
        subject='Welcome to XERXEZ Academy — Your Instructor Account is Ready',
        message=(
            f'Hi {app.full_name},\n\n'
            f'Congratulations! Your application to teach on XERXEZ Academy has been approved.\n\n'
            f'Your login credentials:\n'
            f'  Email: {app.email}\n'
            f'  Password: {password_line}\n\n'
            f'Sign in at: https://xerxez.com/lma/login\n\n'
            f'Welcome to the team!\n\n'
            f'— XERXEZ Academy Team'
        ),
        recipient_list=[app.email],
    )

    return Response({
        'success': True,
        'username': username,
        'email': app.email,
        'message': (
            f'Account created. {app.full_name} can sign in with their chosen password.'
            if use_chosen else f'Account created. Credentials sent to {app.email}.'
        ),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_application(request, app_id):
    """POST /api/v1/lma/instructor/applications/{id}/reject/ — instructor admin only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_instructor_admin(request.user, profile):
        return Response({'error': 'Instructor admin access required.'}, status=403)

    try:
        app = InstructorApplication.objects.get(id=app_id)
    except InstructorApplication.DoesNotExist:
        return Response({'error': 'Application not found.'}, status=404)

    reason = request.data.get('reason', '').strip()
    if not reason:
        return Response({'error': 'A rejection reason is required.'}, status=400)

    # If revoking an approved application, deactivate the instructor account
    if app.status == 'approved':
        revoked_user = User.objects.filter(email=app.email).first()
        if revoked_user:
            try:
                with transaction.atomic():
                    revoked_user.is_active = False
                    revoked_user.save(update_fields=['is_active'])
                    lma_p = getattr(revoked_user, 'lma_profile', None)
                    if lma_p:
                        lma_p.can_access_instructor = False
                        lma_p.save(update_fields=['can_access_instructor'])
            except Exception:
                pass  # non-fatal

    app.status = 'rejected'
    app.rejection_reason = reason
    app.reviewed_at = timezone.now()
    app.reviewed_by = request.user
    app.save(update_fields=['status', 'rejection_reason', 'reviewed_at', 'reviewed_by'])

    _send_safe(
        subject='XERXEZ Academy Application Update',
        message=(
            f'Hi {app.full_name},\n\n'
            f'Thank you for applying to teach on XERXEZ Academy.\n\n'
            f'After careful review, we are unable to approve your application at this time.\n\n'
            f'Feedback from our team:\n{reason}\n\n'
            f'You are welcome to apply again in the future.\n\n'
            f'— XERXEZ Academy Team'
        ),
        recipient_list=[app.email],
    )

    return Response({'success': True})
