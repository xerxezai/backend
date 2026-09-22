from django.db.models import Sum, Avg, Count
from rest_framework import serializers
from apps.core.sanitize import clean_text
from .models import (
    LMAProfile, Course, Module, Lesson,
    Enrollment, Assignment, Submission, Certificate, Review, LessonProgress,
    Quiz, QuizQuestion, QuizAttempt, LessonAssignment, LessonAssignmentSubmission,
)


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'duration', 'order', 'is_free_preview', 'content_type']


class LessonDetailSerializer(serializers.ModelSerializer):
    """Full lesson data — instructor only."""
    assignment = serializers.SerializerMethodField()
    # Plain FileField serialization returns a host-relative path
    # ("/media/lessons/videos/x.mp4") — fine for same-origin <img>/<video> src
    # in production, but the frontend also talks to a separate-origin local
    # dev backend (127.0.0.1:8000), where a relative path resolves against
    # the *frontend's* origin and 404s. Returning an absolute URL (built from
    # this request) makes both cases work without frontend-side origin logic.
    video_file = serializers.SerializerMethodField()
    document_file = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'duration', 'order', 'is_free_preview', 'content', 'video_url',
            'content_type', 'video_file', 'document_file', 'text_content', 'resources',
            'live_session_url', 'live_session_date', 'is_downloadable', 'assignment',
        ]

    def get_assignment(self, obj):
        try:
            return LessonAssignmentSerializer(obj.lesson_assignment).data
        except LessonAssignment.DoesNotExist:
            return None

    def _absolute_file_url(self, file_field):
        if not file_field:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(file_field.url) if request else file_field.url

    def get_video_file(self, obj):
        return self._absolute_file_url(obj.video_file)

    def get_document_file(self, obj):
        return self._absolute_file_url(obj.document_file)


class LessonWriteSerializer(serializers.ModelSerializer):
    # Use CharField instead of URLField so any URL format is accepted
    # (short-form youtu.be/... links, relative paths, etc.)
    video_url = serializers.CharField(allow_blank=True, required=False, default='')
    live_session_url = serializers.CharField(allow_blank=True, required=False, default='')

    class Meta:
        model = Lesson
        fields = [
            'title', 'duration', 'order', 'is_free_preview', 'content', 'video_url',
            'content_type', 'text_content', 'resources',
            'live_session_url', 'live_session_date', 'is_downloadable',
        ]

    def validate_title(self, value):
        return clean_text(value)

    def validate_content(self, value):
        return clean_text(value)

    def validate_text_content(self, value):
        return clean_text(value)


class LessonPublicSerializer(serializers.ModelSerializer):
    """Lesson data for the public course detail endpoint.
    video_url/video_file are NEVER included here — served only via the
    authenticated /lessons/{id}/video/ endpoint after enrollment check."""
    has_video = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()
    has_content = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'duration', 'order', 'is_free_preview', 'content',
            'has_video', 'is_completed', 'content_type', 'has_content',
        ]

    def get_has_video(self, obj):
        return bool(obj.video_url or obj.video_file)

    def get_has_content(self, obj):
        """Whether this lesson actually has content filled in yet for its
        selected type — an instructor can create a lesson with just a title
        and add content later, so the student side needs to distinguish
        "not authored yet" from a genuinely empty/broken lesson."""
        ct = obj.content_type
        if ct == 'video':
            return bool(obj.video_url or obj.video_file)
        if ct == 'document':
            return bool(obj.document_file)
        if ct == 'text':
            return bool(obj.text_content.strip())
        if ct == 'live_session':
            return bool(obj.live_session_url)
        if ct == 'quiz':
            return hasattr(obj, 'quiz') and obj.quiz.questions.exists()
        if ct == 'assignment':
            return hasattr(obj, 'lesson_assignment') and bool(obj.lesson_assignment.description.strip())
        return False

    def get_is_completed(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        return obj.completions.filter(student=user).exists()


class ModuleSerializer(serializers.ModelSerializer):
    """Full module data — for instructor-only endpoints."""
    lessons = LessonDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'description', 'order', 'duration', 'lessons']


class ModulePublicSerializer(serializers.ModelSerializer):
    """Module data for public course detail — video stripped from all lessons."""
    lessons = LessonPublicSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'description', 'order', 'duration', 'lessons']


class ModuleWriteSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(required=False, default=0)
    duration = serializers.IntegerField(required=False, default=0)

    class Meta:
        model = Module
        fields = ['title', 'description', 'order', 'duration']

    def validate_title(self, value):
        return clean_text(value)


# ── Quiz ───────────────────────────────────────────────────────────────────

class QuizQuestionSerializer(serializers.ModelSerializer):
    """Full question data including the correct answer — instructor only."""
    class Meta:
        model = QuizQuestion
        fields = ['id', 'question', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer', 'explanation', 'order']

    def validate_question(self, value):
        return clean_text(value)


class QuizQuestionStudentSerializer(serializers.ModelSerializer):
    """Question data with the answer withheld — used before a student submits."""
    class Meta:
        model = QuizQuestion
        fields = ['id', 'question', 'option_a', 'option_b', 'option_c', 'option_d', 'order']


class QuizSerializer(serializers.ModelSerializer):
    questions = QuizQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = ['id', 'lesson', 'passing_score', 'questions']


class QuizStudentSerializer(serializers.ModelSerializer):
    questions = QuizQuestionStudentSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = ['id', 'lesson', 'passing_score', 'questions']


class QuizAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAttempt
        fields = ['id', 'quiz', 'score', 'passed', 'submitted_at']


# ── Lesson assignment ────────────────────────────────────────────────────────

class LessonAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonAssignment
        fields = ['id', 'lesson', 'title', 'description', 'due_days', 'submission_type']
        read_only_fields = ['lesson']

    def validate_title(self, value):
        return clean_text(value)

    def validate_description(self, value):
        return clean_text(value)


class LessonAssignmentSubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = LessonAssignmentSubmission
        fields = ['id', 'assignment', 'student', 'student_name', 'content', 'file', 'grade', 'feedback', 'submitted_at', 'graded_at']
        read_only_fields = ['student', 'grade', 'feedback', 'graded_at']

    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.username


class CourseListSerializer(serializers.ModelSerializer):
    """
    All dynamic stat fields (total_students, lessons, hours, rating,
    total_ratings, badge) are computed from the real DB at request time.
    The denormalized columns on Course are intentionally ignored.
    """
    instructor_name = serializers.SerializerMethodField()
    total_students  = serializers.SerializerMethodField()
    lessons         = serializers.SerializerMethodField()
    hours           = serializers.SerializerMethodField()
    rating          = serializers.SerializerMethodField()
    total_ratings   = serializers.SerializerMethodField()
    badge           = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'category', 'level', 'price',
            'badge', 'rating', 'total_ratings', 'total_students',
            'hours', 'lessons', 'tech_stack', 'header_color',
            'instructor_name', 'status', 'created_at',
        ]

    def get_instructor_name(self, obj):
        if not obj.instructor:
            return "Unassigned"
        return obj.instructor.get_full_name() or obj.instructor.username

    # ── per-object caches (avoids duplicate queries per field) ────────────
    def _enrolled(self, obj):
        if not hasattr(obj, '_enrolled_cache'):
            obj._enrolled_cache = Enrollment.objects.filter(course=obj).count()
        return obj._enrolled_cache

    def _lesson_stats(self, obj):
        if not hasattr(obj, '_lesson_stats_cache'):
            r = Lesson.objects.filter(module__course=obj).aggregate(
                count=Count('id'), total_mins=Sum('duration')
            )
            obj._lesson_stats_cache = (r['count'] or 0, r['total_mins'] or 0)
        return obj._lesson_stats_cache

    # ── computed fields ───────────────────────────────────────────────────
    def get_total_students(self, obj):
        return self._enrolled(obj)

    def get_lessons(self, obj):
        count, _ = self._lesson_stats(obj)
        return count

    def get_hours(self, obj):
        _, total_mins = self._lesson_stats(obj)
        return round(total_mins / 60, 1)

    def get_rating(self, obj):
        avg = Review.objects.filter(course=obj).aggregate(avg=Avg('rating'))['avg']
        return round(float(avg), 1) if avg else 0.0

    def get_total_ratings(self, obj):
        return Review.objects.filter(course=obj).count()

    def get_badge(self, obj):
        if not obj.badge:
            return ''
        # Don't show badge (e.g. "Bestseller") when there are no real enrollments
        if self._enrolled(obj) == 0:
            return ''
        return obj.badge


class CourseDetailSerializer(CourseListSerializer):
    modules        = ModulePublicSerializer(many=True, read_only=True)
    avg_completion = serializers.SerializerMethodField()
    # Partner branding — sourced from the instructor's LMAProfile, blank when
    # not set (e.g. no company name), so the frontend can conditionally show
    # an "Offered by …" section only when there's something to show.
    instructor_company_name = serializers.SerializerMethodField()
    instructor_website       = serializers.SerializerMethodField()
    instructor_bio           = serializers.SerializerMethodField()
    has_certificate_template = serializers.SerializerMethodField()
    is_instructor             = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'category', 'level', 'price',
            'badge', 'rating', 'total_ratings', 'total_students',
            'hours', 'lessons', 'tech_stack', 'learning_outcomes', 'header_color',
            'instructor_name', 'status', 'created_at', 'updated_at',
            'modules', 'avg_completion',
            'instructor_company_name', 'instructor_website', 'instructor_bio',
            'has_certificate_template', 'is_instructor',
        ]

    def get_has_certificate_template(self, obj):
        return bool(obj.certificate_template)

    def get_is_instructor(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and obj.instructor_id == user.id)

    def get_avg_completion(self, obj):
        enrolled = self._enrolled(obj)
        if enrolled == 0:
            return 0
        lesson_count, _ = self._lesson_stats(obj)
        if lesson_count == 0:
            return 0
        completed = LessonProgress.objects.filter(lesson__module__course=obj).count()
        total_possible = lesson_count * enrolled
        return round(completed / total_possible * 100, 1)

    def _instructor_profile(self, obj):
        if not obj.instructor:
            return None
        return getattr(obj.instructor, 'lma_profile', None)

    def get_instructor_company_name(self, obj):
        profile = self._instructor_profile(obj)
        return profile.company_name if profile else ''

    def get_instructor_website(self, obj):
        profile = self._instructor_profile(obj)
        return profile.website if profile else ''

    def get_instructor_bio(self, obj):
        profile = self._instructor_profile(obj)
        return profile.bio if profile else ''


class EnrollmentSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_level = serializers.CharField(source='course.level', read_only=True)
    course_instructor = serializers.SerializerMethodField()
    course_header_color = serializers.CharField(source='course.header_color', read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            'id', 'course', 'course_title', 'course_level', 'course_instructor',
            'course_header_color', 'progress', 'enrolled_at', 'completed', 'completed_at',
        ]

    def get_course_instructor(self, obj):
        return obj.course.instructor.username if obj.course.instructor else 'Unassigned'


class AssignmentSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Assignment
        fields = ['id', 'course', 'course_title', 'title', 'description', 'due_date', 'created_at']


class SubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)

    class Meta:
        model = Submission
        fields = [
            'id', 'assignment', 'assignment_title', 'student', 'student_name',
            'content', 'grade', 'feedback', 'submitted_at', 'graded_at',
        ]

    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.username


class CertificateSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    student_name = serializers.SerializerMethodField()
    certificate_file = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = ['id', 'course', 'course_title', 'student_name', 'issued_at', 'certificate_file', 'unique_id']

    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.username

    def get_certificate_file(self, obj):
        if not obj.certificate_file:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.certificate_file.url) if request else obj.certificate_file.url


class ReviewSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'course', 'student', 'student_name', 'rating', 'comment', 'created_at']
        read_only_fields = ['student']

    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.username


class StudentDashboardSerializer(serializers.Serializer):
    name = serializers.CharField()
    enrollments = EnrollmentSerializer(many=True)
    certificates = CertificateSerializer(many=True)
    pending_assignments = AssignmentSerializer(many=True)
    stats = serializers.DictField()


class InstructorDashboardSerializer(serializers.Serializer):
    name = serializers.CharField()
    courses = CourseListSerializer(many=True)
    pending_submissions = SubmissionSerializer(many=True)
    stats = serializers.DictField()


class CourseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            'title', 'description', 'category', 'level', 'price',
            'badge', 'header_color', 'tech_stack', 'learning_outcomes', 'status',
        ]

    def validate_title(self, value):
        return clean_text(value)

    def validate_description(self, value):
        return clean_text(value)

    def validate_learning_outcomes(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Must be a list of strings.')
        cleaned = [clean_text(str(v)).strip() for v in value if str(v).strip()]
        if len(cleaned) > 8:
            raise serializers.ValidationError('Up to 8 learning outcomes only.')
        return cleaned
