from rest_framework import serializers
from .models import (
    LMAProfile, Course, Module, Lesson,
    Enrollment, Assignment, Submission, Certificate, Review,
)


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'duration', 'order', 'is_free_preview']


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'order', 'duration', 'lessons']


class CourseListSerializer(serializers.ModelSerializer):
    instructor_name = serializers.SerializerMethodField()

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


class CourseDetailSerializer(serializers.ModelSerializer):
    modules = ModuleSerializer(many=True, read_only=True)
    instructor_name = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'category', 'level', 'price',
            'badge', 'rating', 'total_ratings', 'total_students',
            'hours', 'lessons', 'tech_stack', 'header_color',
            'instructor_name', 'status', 'created_at', 'updated_at',
            'modules',
        ]

    def get_instructor_name(self, obj):
        return obj.instructor.get_full_name() or obj.instructor.username


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
