"""
LMA (Learning Management Application) Views
"""
import logging

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings as django_settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)

from .models import (
    LMAProfile, Course, Module, Lesson, Enrollment, Assignment,
    Submission, Certificate, Review, LessonProgress, Notification,
    InstructorApplication,
)
from .serializers import (
    CourseListSerializer, CourseDetailSerializer, EnrollmentSerializer,
    AssignmentSerializer, SubmissionSerializer, CertificateSerializer,
    ReviewSerializer, CourseCreateSerializer,
    ModuleSerializer, ModuleWriteSerializer,
    LessonDetailSerializer, LessonWriteSerializer,
)

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


def _lma_token(user):
    return str(AccessToken.for_user(user))


def _send_safe(subject, message, recipient_list):
    """send_mail wrapped so email failures never break the main request."""
    try:
        from_email = getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'xerxez.in@gmail.com')
        send_mail(subject, message, from_email, recipient_list, fail_silently=True)
    except Exception as exc:
        logger.warning('LMA email failed: %s', exc)


# ── Auth ────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
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
        return Response({'error': 'Invalid credentials.'}, status=401)

    if not user.is_active:
        return Response({'error': 'Account is inactive.'}, status=401)

    profile = _get_or_create_lma_profile(user)

    if role == 'instructor' and not profile.can_access_instructor:
        return Response(
            {'error': "You don't have instructor access. Contact admin to request access."},
            status=403,
        )

    token = _lma_token(user)
    name = user.get_full_name() or user.username

    return Response({
        'lma_token': token,
        'lma_role': role,
        'can_access_student': profile.can_access_student,
        'can_access_instructor': profile.can_access_instructor,
        'instructor_level': profile.instructor_level,
        'name': name,
        'user_id': user.id,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
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

    return Response({
        'lma_token': _lma_token(user),
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
    return Response(CourseDetailSerializer(course).data)


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
    pending_submissions = Submission.objects.filter(
        assignment__course_id__in=course_ids,
        grade__isnull=True,
    ).select_related('assignment', 'student')[:20]

    total_students = sum(c.total_students for c in courses)

    stats = {
        'total_courses': courses.count(),
        'total_students': total_students,
        'pending_reviews': courses.filter(status='pending_review').count(),
    }
    if is_super_user:
        total_revenue = sum(float(c.price) * c.total_students for c in courses)
        stats['total_earnings'] = round(total_revenue, 2)

    return Response({
        'name': user.get_full_name() or user.username,
        'instructor_level': profile.instructor_level,
        'stats': stats,
        'courses': CourseListSerializer(courses, many=True).data,
        'pending_submissions': SubmissionSerializer(pending_submissions, many=True).data,
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

    submission, created = Submission.objects.get_or_create(
        assignment=assignment,
        student=request.user,
        defaults={'content': request.data.get('content', '')},
    )
    if not created:
        submission.content = request.data.get('content', submission.content)
        submission.submitted_at = timezone.now()
        submission.save()

    return Response(SubmissionSerializer(submission).data, status=201 if created else 200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def enrollment_status(request, course_id):
    """GET /api/v1/lma/enrollment-status/{course_id}/"""
    enrolled = Enrollment.objects.filter(student=request.user, course_id=course_id).exists()
    return Response({'enrolled': enrolled})


@api_view(['GET'])
@permission_classes([AllowAny])
def lesson_video_url(request, lesson_id):
    """GET /api/v1/lma/lessons/{lesson_id}/video/"""
    try:
        lesson = Lesson.objects.select_related('module__course').get(id=lesson_id)
    except Lesson.DoesNotExist:
        return Response({'error': 'Lesson not found.'}, status=status.HTTP_404_NOT_FOUND)

    course = lesson.module.course

    if lesson.is_free_preview:
        return Response({'video_url': lesson.video_url})

    if not request.user.is_authenticated:
        return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

    user = request.user
    profile = _get_or_create_lma_profile(user)
    is_instructor = profile.can_access_instructor or course.instructor == user
    is_enrolled = Enrollment.objects.filter(student=user, course=course).exists()

    if not (is_enrolled or is_instructor):
        return Response({'error': 'Enrollment required to watch this lesson.'},
                        status=status.HTTP_403_FORBIDDEN)

    return Response({'video_url': lesson.video_url})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def lesson_complete(request, lesson_id):
    """POST /api/v1/lma/lessons/{lesson_id}/complete/"""
    try:
        lesson = Lesson.objects.select_related('module__course').get(id=lesson_id)
    except Lesson.DoesNotExist:
        return Response({'error': 'Lesson not found.'}, status=404)

    course = lesson.module.course
    try:
        enrollment = Enrollment.objects.get(student=request.user, course=course)
    except Enrollment.DoesNotExist:
        return Response({'error': 'Not enrolled in this course.'}, status=403)

    LessonProgress.objects.get_or_create(student=request.user, lesson=lesson)

    total_lessons = Lesson.objects.filter(module__course=course).count()
    completed_count = LessonProgress.objects.filter(
        student=request.user, lesson__module__course=course
    ).count()

    new_progress = int((completed_count / max(total_lessons, 1)) * 100)
    enrollment.progress = new_progress
    if new_progress >= 100:
        enrollment.completed = True
        if not enrollment.completed_at:
            enrollment.completed_at = timezone.now()
        Certificate.objects.get_or_create(student=request.user, course=course)
    enrollment.save(update_fields=['progress', 'completed', 'completed_at'])

    return Response({
        'completed': True,
        'progress': new_progress,
        'course_completed': enrollment.completed,
    })


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
        })

    name = request.data.get('name', '').strip()
    email = request.data.get('email', '').strip().lower()
    phone = request.data.get('phone', '').strip()
    bio = request.data.get('bio', '').strip()

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
        return Response(ModuleSerializer(modules, many=True).data)

    serializer = ModuleWriteSerializer(data=request.data)
    if serializer.is_valid():
        module = serializer.save(course=course)
        return Response(ModuleSerializer(module).data, status=201)
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
        return Response(ModuleSerializer(module).data)
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
        return Response(LessonDetailSerializer(lessons, many=True).data)

    serializer = LessonWriteSerializer(data=request.data)
    if serializer.is_valid():
        lesson = serializer.save(module=module)
        return Response(LessonDetailSerializer(lesson).data, status=201)
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
        return Response(LessonDetailSerializer(lesson).data)

    if request.method == 'DELETE':
        lesson.delete()
        return Response({'success': True})

    serializer = LessonWriteSerializer(lesson, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(LessonDetailSerializer(lesson).data)
    return Response(serializer.errors, status=400)


# ── Instructor — students / reviews / analytics ──────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_students(request):
    """GET /api/v1/lma/instructor/students/"""
    profile = _get_or_create_lma_profile(request.user)
    if not profile.can_access_instructor:
        return Response({'error': 'Instructor access required.'}, status=403)

    course_qs = (
        Course.objects.all() if _is_super(profile)
        else Course.objects.filter(instructor=request.user)
    )
    course_ids = course_qs.values_list('id', flat=True)
    enrollments = (
        Enrollment.objects.filter(course_id__in=course_ids)
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
    """GET /api/v1/lma/instructor/instructors/ — list all instructors."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_super(profile):
        return Response({'error': 'Super instructor access required.'}, status=403)

    instructor_profiles = LMAProfile.objects.filter(
        can_access_instructor=True
    ).select_related('user').order_by('instructor_level', 'user__date_joined')

    data = [{
        'id': p.user.id,
        'name': p.user.get_full_name() or p.user.username,
        'email': p.user.email,
        'username': p.user.username,
        'instructor_level': p.instructor_level,
        'date_joined': p.user.date_joined.isoformat(),
        'course_count': Course.objects.filter(instructor=p.user).count(),
    } for p in instructor_profiles]
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_instructor(request):
    """POST /api/v1/lma/instructor/create-instructor/ — super only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_super(profile):
        return Response({'error': 'Super instructor access required.'}, status=403)

    name = request.data.get('name', '').strip()
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')
    bio = request.data.get('bio', '').strip()

    if not name or not email or not password:
        return Response({'error': 'Name, email and password are required.'}, status=400)
    if len(password) < 6:
        return Response({'error': 'Password must be at least 6 characters.'}, status=400)
    if not _re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return Response({'error': 'Enter a valid email address.'}, status=400)
    if User.objects.filter(email=email).exists():
        return Response({'error': 'An account with this email already exists.'}, status=400)

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
                is_active=True,
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
    }, status=201)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_instructor(request, instructor_id):
    """PUT /api/v1/lma/instructor/instructors/{id}/ — super only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_super(profile):
        return Response({'error': 'Super instructor access required.'}, status=403)

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

    # Validate level value
    if new_level and new_level not in ('regular', 'super'):
        return Response({'error': 'instructor_level must be "regular" or "super".'}, status=400)

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
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_instructor(request, instructor_id):
    """DELETE /api/v1/lma/instructor/instructors/{id}/ — super only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_super(profile):
        return Response({'error': 'Super instructor access required.'}, status=403)

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
    """GET /api/v1/lma/instructor/instructors/{id}/courses/ — super only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_super(profile):
        return Response({'error': 'Super instructor access required.'}, status=403)

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
    """POST /api/v1/lma/instructor/instructors/{id}/reset-password/ — super only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_super(profile):
        return Response({'error': 'Super instructor access required.'}, status=403)

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
    """PUT /api/v1/lma/courses/{id}/publish/ — super only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_super(profile):
        return Response({'error': 'Super instructor access required.'}, status=403)

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

    # Notify instructor in-app
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
    """PUT /api/v1/lma/courses/{id}/reject/ — super only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_super(profile):
        return Response({'error': 'Super instructor access required.'}, status=403)

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

    # Notify instructor in-app
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
    if not _is_super(profile):
        return Response({'error': 'Super instructor access required.'}, status=403)

    courses = Course.objects.filter(
        status='pending_review'
    ).select_related('instructor').order_by('-updated_at')

    data = [{
        'id': c.id,
        'title': c.title,
        'description': c.description[:200],
        'instructor_name': c.instructor.get_full_name() or c.instructor.username,
        'instructor_email': c.instructor.email,
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


@api_view(['POST'])
@permission_classes([AllowAny])
def become_instructor(request):
    """POST /api/v1/lma/become-instructor/ — public, no auth required."""
    full_name = request.data.get('full_name', '').strip()
    email     = request.data.get('email', '').strip().lower()
    phone     = request.data.get('phone', '').strip()
    expertise = request.data.get('expertise', '').strip()
    bio       = request.data.get('bio', '').strip()
    why_teach = request.data.get('why_teach', '').strip()
    password  = request.data.get('password', '')

    if not full_name or not email or not bio or not why_teach:
        return Response({'error': 'Full name, email, bio, and why_teach are required.'}, status=400)
    if not password or len(password) < 6:
        return Response({'error': 'Password must be at least 6 characters.'}, status=400)
    if not _re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return Response({'error': 'Enter a valid email address.'}, status=400)
    if len(bio) < 30:
        return Response({'error': 'Bio must be at least 30 characters.'}, status=400)
    if len(why_teach) < 50:
        return Response({'error': 'Why-teach must be at least 50 characters.'}, status=400)

    if InstructorApplication.objects.filter(email=email).exists():
        return Response({'error': 'An application with this email already exists.'}, status=400)
    if User.objects.filter(email=email).exists():
        return Response({'error': 'This email is already registered. Please sign in.'}, status=400)

    from django.contrib.auth.hashers import make_password
    app = InstructorApplication.objects.create(
        full_name=full_name, email=email, phone=phone,
        expertise=expertise, bio=bio, why_teach=why_teach,
        password_hash=make_password(password),
    )

    # Notify super instructors in-app
    for su in _get_super_users():
        Notification.objects.create(
            recipient=su,
            title='New Instructor Application',
            message=f'{full_name} ({email}) has applied to become an instructor.',
        )

    # Email super instructors
    _send_safe(
        subject=f'[Xerxez LMA] New Instructor Application from {full_name}',
        message=(
            f'Hello,\n\n'
            f'{full_name} ({email}) has submitted an instructor application.\n\n'
            f'Expertise: {expertise or "Not specified"}\n\n'
            f'Bio:\n{bio}\n\n'
            f'Why teach:\n{why_teach}\n\n'
            f'Log in to the instructor dashboard → Applications to review.\n\n'
            f'— Xerxez LMA'
        ),
        recipient_list=SUPER_INSTRUCTOR_EMAILS,
    )

    return Response({'success': True, 'application_id': app.id}, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_applications(request):
    """GET /api/v1/lma/instructor/applications/?status=pending"""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_super(profile):
        return Response({'error': 'Super instructor access required.'}, status=403)

    status_filter = request.query_params.get('status', '')
    qs = InstructorApplication.objects.all()
    if status_filter in ('pending', 'approved', 'rejected'):
        qs = qs.filter(status=status_filter)

    pending_count = InstructorApplication.objects.filter(status='pending').count()
    data = [{
        'id': a.id,
        'full_name': a.full_name,
        'email': a.email,
        'phone': a.phone,
        'expertise': a.expertise,
        'bio': a.bio,
        'why_teach': a.why_teach,
        'status': a.status,
        'rejection_reason': a.rejection_reason,
        'applied_at': a.applied_at.isoformat(),
        'reviewed_at': a.reviewed_at.isoformat() if a.reviewed_at else None,
        'reviewed_by': a.reviewed_by.get_full_name() or a.reviewed_by.username if a.reviewed_by else None,
    } for a in qs]
    return Response({'applications': data, 'pending_count': pending_count})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_application(request, app_id):
    """POST /api/v1/lma/instructor/applications/{id}/approve/ — super only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_super(profile):
        return Response({'error': 'Super instructor access required.'}, status=403)

    try:
        app = InstructorApplication.objects.get(id=app_id)
    except InstructorApplication.DoesNotExist:
        return Response({'error': 'Application not found.'}, status=404)

    import secrets
    import string

    existing_user = User.objects.filter(email=app.email).first()

    if existing_user:
        # Re-approving a previously rejected application whose account already exists —
        # re-activate the account, restore instructor profile, and send a new temp password.
        import secrets as _sec
        alphabet = string.ascii_letters + string.digits + '!@#$'
        raw_password = ''.join(_sec.choice(alphabet) for _ in range(14))
        reuse_chosen = bool(app.password_hash)
        try:
            with transaction.atomic():
                existing_user.is_active = True
                if reuse_chosen:
                    existing_user.password = app.password_hash
                else:
                    existing_user.set_password(raw_password)
                existing_user.save(update_fields=['is_active', 'password'])

                lma_profile, _ = LMAProfile.objects.get_or_create(user=existing_user)
                lma_profile.lma_role = 'instructor'
                lma_profile.can_access_student = False
                lma_profile.can_access_instructor = True
                lma_profile.instructor_level = 'regular'
                lma_profile.save()

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
                + ('  Password: the password you chose when applying\n\n' if reuse_chosen
                   else f'  Password: {raw_password}\n\n')
                + f'Sign in at: https://xerxez.com/lma/login\n\n'
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
    # If the applicant chose a password at apply time, reuse its stored hash;
    # otherwise generate a temporary one to email.
    alphabet = string.ascii_letters + string.digits + '!@#$'
    raw_password = ''.join(secrets.choice(alphabet) for _ in range(14))
    use_chosen = bool(app.password_hash)

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

            lma_profile, _ = LMAProfile.objects.get_or_create(user=user)
            lma_profile.lma_role = 'instructor'
            lma_profile.can_access_student = False
            lma_profile.can_access_instructor = True
            lma_profile.instructor_level = 'regular'
            lma_profile.bio = app.bio
            lma_profile.save()

            app.status = 'approved'
            app.reviewed_at = timezone.now()
            app.reviewed_by = request.user
            app.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
    except Exception as exc:
        return Response({'error': f'Could not create instructor account: {exc}'}, status=400)

    if use_chosen:
        cred_lines = (
            f'  Email: {app.email}\n'
            f'  Password: the password you chose when applying\n\n'
        )
    else:
        cred_lines = (
            f'  Email: {app.email}\n'
            f'  Password: {raw_password}\n\n'
        )
    _send_safe(
        subject='Welcome to XERXEZ Academy — Your Instructor Account',
        message=(
            f'Hi {app.full_name},\n\n'
            f'Congratulations! Your application to teach on XERXEZ Academy has been approved.\n\n'
            f'Your login credentials:\n'
            + cred_lines +
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
    """POST /api/v1/lma/instructor/applications/{id}/reject/ — super only."""
    profile = _get_or_create_lma_profile(request.user)
    if not _is_super(profile):
        return Response({'error': 'Super instructor access required.'}, status=403)

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
        subject='Your XERXEZ Academy Instructor Application',
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
