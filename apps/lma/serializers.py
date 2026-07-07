from django.db.models import Sum, Avg, Count
from rest_framework import serializers
from .models import (
    LMAProfile, Course, Module, Lesson,
    Enrollment, Assignment, Submission, Certificate, Review, LessonProgress,
)


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'duration', 'order', 'is_free_preview']


class LessonDetailSerializer(serializers.ModelSerializer):
    """Full lesson data including content + video_url — instructor only."""
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'duration', 'order', 'is_free_preview', 'content', 'video_url']


class LessonWriteSerializer(serializers.ModelSerializer):
    # Use CharField instead of URLField so any URL format is accepted
    # (short-form youtu.be/... links, relative paths, etc.)
    video_url = serializers.CharField(allow_blank=True, required=False, default='')

    class Meta:
        model = Lesson
        fields = ['title', 'duration', 'order', 'is_free_preview', 'content', 'video_url']


class LessonPublicSerializer(serializers.ModelSerializer):
    """Lesson data for the public course detail endpoint.
    video_url is NEVER included here — it is served only via the
    authenticated /lessons/{id}/video/ endpoint after enrollment check."""
    has_video = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'duration', 'order', 'is_free_preview', 'content', 'has_video']

    def get_has_video(self, obj):
        return bool(obj.video_url)


class ModuleSerializer(serializers.ModelSerializer):
    """Full module data including video_url — for instructor-only endpoints."""
    lessons = LessonDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'order', 'duration', 'lessons']


class ModulePublicSerializer(serializers.ModelSerializer):
    """Module data for public course detail — video_url stripped from all lessons."""
    lessons = LessonPublicSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'order', 'duration', 'lessons']


class ModuleWriteSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(required=False, default=0)
    duration = serializers.IntegerField(required=False, default=0)

    class Meta:
        model = Module
        fields = ['title', 'order', 'duration']


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

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'category', 'level', 'price',
            'badge', 'rating', 'total_ratings', 'total_students',
            'hours', 'lessons', 'tech_stack', 'header_color',
            'instructor_name', 'status', 'created_at', 'updated_at',
            'modules', 'avg_completion',
        ]

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
        return obj.course.instructor.username


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

    class Meta:
        model = Certificate
        fields = ['id', 'course', 'course_title', 'issued_at']


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
            'badge', 'header_color', 'tech_stack', 'status',
        ]
