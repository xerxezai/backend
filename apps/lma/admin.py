from django.contrib import admin
from .models import LMAProfile, Course, Module, Lesson, Enrollment, Assignment, Submission, Certificate, Review


@admin.register(LMAProfile)
class LMAProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'lma_role', 'can_access_student', 'can_access_instructor', 'created_at']
    list_filter = ['lma_role', 'can_access_instructor']
    search_fields = ['user__username', 'user__email']


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'instructor', 'category', 'level', 'price', 'status', 'total_students', 'rating']
    list_filter = ['status', 'level', 'category']
    search_fields = ['title', 'instructor__username']
    inlines = [ModuleInline]


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order', 'duration']
    inlines = [LessonInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'progress', 'completed', 'enrolled_at']
    list_filter = ['completed']


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'due_date']


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['student', 'assignment', 'grade', 'submitted_at', 'graded_at']


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'issued_at']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'rating', 'created_at']
