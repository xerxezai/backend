"""
LMA (Learning Management Application) Views
"""
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)

from .models import (
    LMAProfile, Course, Module, Lesson, Enrollment, Assignment,
    Submission, Certificate, Review, LessonProgress,
)
from .serializers import (
    CourseListSerializer, CourseDetailSerializer, EnrollmentSerializer,
    AssignmentSerializer, SubmissionSerializer, CertificateSerializer,
    ReviewSerializer, CourseCreateSerializer,
    ModuleSerializer, ModuleWriteSerializer,
    LessonDetailSerializer, LessonWriteSerializer,
)

User = get_user_model()

INSTRUCTOR_USERNAMES = {'danish', 'tanzeem'}   # matched case-insensitively via .lower()
INSTRUCTOR_EMAILS    = {
    'danish@xerxez.com',
    'tanzeem@xerxez.com',
    'xerxez.in@gmail.com',   # Tanzeem alternate (create_superusers default)
}


import re as _re


def _get_or_create_lma_profile(user):
    profile, _ = LMAProfile.objects.get_or_create(user=user)
    is_instructor = (
        user.username.lower() in INSTRUCTOR_USERNAMES or
        user.email.lower() in INSTRUCTOR_EMAILS
    )
    if is_instructor:
        profile.lma_role = 'both'
        profile.can_access_student = True
        profile.can_access_instructor = True
        profile.save()
    return profile


def _lma_token(user):
    # AccessToken is stateless — no OutstandingToken DB write, so no FK
    # constraint issue between token_blacklist_outstandingtoken and auth_user.
    return str(AccessToken.for_user(user))


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

    # Find user by email (case-insensitive) or username
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
        # Multiple accounts share the same email — match on exact username fallback
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

    # Generate unique username from email prefix
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
            user._skip_profile_signal = True  # skip ERP UserProfile signal
            user.save()

            # get_or_create in case the post_save signal already created one
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
    """POST /api/v1/lma/mock-payment/{course_id}/ — simulates payment then enrolls."""
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


# ── Instructor ───────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_dashboard(request):
    """GET /api/v1/lma/instructor/dashboard/
    Admin instructors (Danish/Tanzeem) see ALL courses; others see only their own.
    """
    user = request.user
    profile = _get_or_create_lma_profile(user)
    courses = (Course.objects.all() if profile.can_access_instructor
               else Course.objects.filter(instructor=user)).order_by('-created_at')
    course_ids = courses.values_list('id', flat=True)

    pending_submissions = Submission.objects.filter(
        assignment__course_id__in=course_ids,
        grade__isnull=True,
    ).select_related('assignment', 'student')[:20]

    total_students = sum(c.total_students for c in courses)
    total_revenue = sum(float(c.price) * c.total_students for c in courses)

    return Response({
        'name': user.get_full_name() or user.username,
        'stats': {
            'total_courses': courses.count(),
            'total_students': total_students,
            'pending_reviews': pending_submissions.count(),
            'total_earnings': round(total_revenue, 2),
        },
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

    serializer = CourseCreateSerializer(data=request.data)
    if serializer.is_valid():
        course = serializer.save(instructor=request.user)
        return Response(CourseListSerializer(course).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_course(request, course_id):
    """PUT /api/v1/lma/courses/{id}/update/"""
    profile = _get_or_create_lma_profile(request.user)
    try:
        qs = Course.objects.all() if profile.can_access_instructor else Course.objects.filter(instructor=request.user)
        course = qs.get(id=course_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found.'}, status=404)

    serializer = CourseCreateSerializer(course, data=request.data, partial=True)
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
    """GET /api/v1/lma/lessons/{lesson_id}/video/

    Returns the video_url for a lesson if the requester is authorized.
    Free-preview lessons: any request (even unauthenticated) succeeds.
    All other lessons: requester must be authenticated AND enrolled OR an instructor.
    """
    try:
        lesson = Lesson.objects.select_related('module__course').get(id=lesson_id)
    except Lesson.DoesNotExist:
        return Response({'error': 'Lesson not found.'}, status=status.HTTP_404_NOT_FOUND)

    course = lesson.module.course

    if lesson.is_free_preview:
        logger.info('LMA video access (free preview): lesson=%s course=%s user=%s',
                    lesson.id, course.id,
                    request.user.id if request.user.is_authenticated else 'anon')
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

    logger.info('LMA video access: user=%s lesson=%s course=%s instructor=%s',
                user.id, lesson.id, course.id, is_instructor)
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
    """GET /api/v1/lma/student/my-courses/ — Full enrollment list, no limit."""
    enrollments = (
        Enrollment.objects.filter(student=request.user)
        .select_related('course', 'course__instructor')
        .order_by('-enrolled_at')
    )
    return Response(EnrollmentSerializer(enrollments, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_assignments(request):
    """GET /api/v1/lma/student/assignments/ — All assignments with submission status."""
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
    """GET /api/v1/lma/student/progress/ — Progress report with time-series."""
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
    """GET /api/v1/lma/courses/browse/ — Published courses excluding enrolled."""
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
    courses = (Course.objects.all() if profile.can_access_instructor
               else Course.objects.filter(instructor=request.user)).order_by('-created_at')
    return Response(CourseListSerializer(courses, many=True).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_course(request, course_id):
    """DELETE /api/v1/lma/courses/{id}/delete/"""
    profile = _get_or_create_lma_profile(request.user)
    try:
        qs = Course.objects.all() if profile.can_access_instructor else Course.objects.filter(instructor=request.user)
        course = qs.get(id=course_id)
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
        qs = Course.objects.all() if profile.can_access_instructor else Course.objects.filter(instructor=request.user)
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
        if not profile.can_access_instructor:
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
        if not profile.can_access_instructor:
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
        if not profile.can_access_instructor:
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

    course_qs = Course.objects.all() if profile.can_access_instructor else Course.objects.filter(instructor=request.user)
    course_ids = course_qs.values_list('id', flat=True)
    enrollments = (
        Enrollment.objects.filter(course_id__in=course_ids)
        .select_related('student', 'course')
        .order_by('-enrolled_at')
    )
    data = [{
        'id': e.id,
        'student_name': e.student.get_full_name() or e.student.username,
        'student_email': e.student.email,
        'course_title': e.course.title,
        'enrolled_at': e.enrolled_at.isoformat(),
        'progress': e.progress,
        'completed': e.completed,
    } for e in enrollments]
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_reviews(request):
    """GET /api/v1/lma/instructor/reviews/"""
    profile = _get_or_create_lma_profile(request.user)
    course_qs = Course.objects.all() if profile.can_access_instructor else Course.objects.filter(instructor=request.user)
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
    courses = (Course.objects.all() if profile.can_access_instructor
               else Course.objects.filter(instructor=request.user)).order_by('-created_at')
    data = []
    for c in courses:
        enrollments = Enrollment.objects.filter(course=c)
        completed = enrollments.filter(completed=True).count()
        total = enrollments.count()
        avg_rating = Review.objects.filter(course=c).aggregate(avg=Avg('rating'))['avg'] or 0
        data.append({
            'id': c.id,
            'title': c.title,
            'total_students': c.total_students,
            'completed': completed,
            'completion_rate': round((completed / max(total, 1)) * 100, 1),
            'avg_rating': round(float(avg_rating), 1),
            'revenue': round(float(c.price) * c.total_students, 2),
            'status': c.status,
        })
    return Response(data)
