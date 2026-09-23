import uuid

from django.conf import settings
from django.db import models


class LMAProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('instructor', 'Instructor'),
        ('both', 'Both'),
    ]
    LEVEL_CHOICES = [
        ('super', 'Super Instructor'),
        ('regular', 'Regular Instructor'),
    ]
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lma_profile',
    )
    lma_role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    can_access_student = models.BooleanField(default=True)
    can_access_instructor = models.BooleanField(default=False)
    instructor_level = models.CharField(
        max_length=20, choices=LEVEL_CHOICES, default='super',
    )
    bio = models.TextField(blank=True, default='')
    # Partner branding, shown on the course detail page ("Offered by …") when
    # set — populated from the instructor's InstructorApplication at approval
    # time, editable later from the instructor's own profile page.
    company_name = models.CharField(max_length=200, blank=True, default='')
    website = models.URLField(blank=True, default='')
    linkedin_url = models.URLField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.lma_role})"


class Course(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_review', 'Pending Review'),
        ('published', 'Published'),
        ('rejected', 'Rejected'),
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='courses',
        null=True, blank=True,
    )
    category = models.CharField(max_length=100)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    badge = models.CharField(max_length=50, blank=True)
    header_color = models.CharField(max_length=20, default='cream')
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    total_ratings = models.IntegerField(default=0)
    total_students = models.IntegerField(default=0)
    hours = models.IntegerField(default=0)
    lessons = models.IntegerField(default=0)
    tech_stack = models.JSONField(default=list)
    # Up to 8 short bullet points set by the instructor — "What you'll learn" on
    # the course detail page. Plain list of strings, e.g. ["Deploy models to
    # production", "Build CI/CD pipelines for ML", ...].
    learning_outcomes = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    rejection_reason = models.TextField(blank=True, default='')
    # Instructor-uploaded background used to render each student's
    # certificate of completion — see Certificate.certificate_file.
    certificate_template = models.FileField(
        upload_to='certificates/templates/',
        blank=True, null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    order = models.IntegerField(default=0)
    duration = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Lesson(models.Model):
    CONTENT_TYPE_CHOICES = [
        ('video', 'Video'),
        ('document', 'Document/PDF'),
        ('quiz', 'Quiz'),
        ('assignment', 'Assignment'),
        ('live_session', 'Live Session'),
        ('text', 'Text/Article'),
    ]

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    duration = models.IntegerField(default=0)
    order = models.IntegerField(default=0)
    is_free_preview = models.BooleanField(default=False)
    content = models.TextField(blank=True)
    video_url = models.URLField(blank=True, default='')

    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, default='video')

    # Video
    video_file = models.FileField(upload_to='lessons/videos/', blank=True, null=True)

    # Document
    document_file = models.FileField(upload_to='lessons/documents/', blank=True, null=True)

    # Text/Article
    text_content = models.TextField(blank=True, default='')

    # Resources — [{name, url, type}]
    resources = models.JSONField(default=list, blank=True)

    # Live session
    live_session_url = models.URLField(blank=True, default='')
    live_session_date = models.DateTimeField(null=True, blank=True)

    # Settings
    is_downloadable = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.module.title} - {self.title}"


class Enrollment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    progress = models.IntegerField(default=0)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Razorpay payment trail — blank for free-course enrollments (no order
    # was ever created) and for enrollments made before this field existed.
    razorpay_order_id = models.CharField(max_length=100, blank=True, default='')
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default='')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ['student', 'course']

    def __str__(self):
        return f"{self.student.username} → {self.course.title}"


class Assignment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    content = models.TextField(blank=True)
    grade = models.IntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student.username} - {self.assignment.title}"


class Certificate(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='certificates',
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='certificates')
    issued_at = models.DateTimeField(auto_now_add=True)
    certificate_file = models.FileField(upload_to='certificates/issued/', blank=True, null=True)
    unique_id = models.UUIDField(default=uuid.uuid4, unique=True)

    class Meta:
        unique_together = ['student', 'course']

    def __str__(self):
        return f"{self.student.username} - {self.course.title}"


class Review(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    rating = models.IntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'course']

    def __str__(self):
        return f"{self.student.username} - {self.course.title} ({self.rating}★)"


class LessonProgress(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lesson_progress',
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='completions')
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'lesson']

    def __str__(self):
        return f"{self.student.username} ✓ {self.lesson.title}"


class InstructorApplication(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    APPLICANT_TYPE_CHOICES = [
        ('individual', 'Individual Instructor'),
        ('company',    'Company / Organisation'),
    ]
    applicant_type   = models.CharField(max_length=20, choices=APPLICANT_TYPE_CHOICES, default='individual')
    company_size     = models.CharField(max_length=20, blank=True, default='')
    full_name        = models.CharField(max_length=200)
    company_name     = models.CharField(max_length=200, blank=True, default='')
    email            = models.EmailField(unique=True)
    phone            = models.CharField(max_length=30, blank=True, default='')
    linkedin_url     = models.URLField(blank=True, default='')
    website          = models.URLField(blank=True, default='')
    expertise        = models.CharField(max_length=200, blank=True, default='')
    years_experience = models.IntegerField(default=0)
    bio              = models.TextField(blank=True, default='')
    previous_teaching_experience = models.BooleanField(default=False)
    why_teach        = models.TextField(blank=True, default='')
    proposed_course_title = models.CharField(max_length=200, blank=True, default='')
    course_description     = models.TextField(blank=True, default='')
    target_audience         = models.CharField(max_length=300, blank=True, default='')
    estimated_duration      = models.CharField(max_length=100, blank=True, default='')
    agree_terms      = models.BooleanField(default=False)
    confirm_rights   = models.BooleanField(default=False)
    password_hash    = models.CharField(max_length=256, blank=True, default='')
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, default='')
    applied_at       = models.DateTimeField(auto_now_add=True)
    reviewed_at      = models.DateTimeField(null=True, blank=True)
    reviewed_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_applications',
    )

    class Meta:
        db_table = 'lma_instructor_application'
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.full_name} <{self.email}> [{self.status}]"


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=200)
    message = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(
        Course, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='notifications',
    )

    class Meta:
        db_table = 'lma_notification'
        ordering = ['-created_at']

    def __str__(self):
        return f"→{self.recipient.username}: {self.title}"


class Quiz(models.Model):
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='quiz')
    passing_score = models.PositiveIntegerField(default=70)  # percentage

    def __str__(self):
        return f"Quiz for {self.lesson.title}"


class QuizQuestion(models.Model):
    ANSWER_CHOICES = [('a', 'A'), ('b', 'B'), ('c', 'C'), ('d', 'D')]

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_answer = models.CharField(max_length=1, choices=ANSWER_CHOICES)
    explanation = models.TextField(blank=True, default='')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.question[:60]


class QuizAttempt(models.Model):
    """One student's attempt at a lesson quiz — records score and pass/fail
    so `lesson_complete`-style progress checks can gate on quiz completion."""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts',
    )
    answers = models.JSONField(default=dict)  # {question_id: 'a'|'b'|'c'|'d'}
    score = models.PositiveIntegerField(default=0)  # percentage
    passed = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} — {self.quiz.lesson.title} ({self.score}%)"


class LessonAssignment(models.Model):
    """A lesson-scoped assignment (one of the six lesson content types) —
    distinct from the course-level `Assignment`/`Submission` pair above,
    which predates this feature and is tied to a Course, not a Lesson."""
    SUBMISSION_TYPE_CHOICES = [
        ('text', 'Text submission'),
        ('file', 'File upload'),
        ('url', 'URL/Link'),
        ('code', 'Code submission'),
    ]

    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='lesson_assignment')
    # Blank/default so an instructor can save an assignment shell (or none at
    # all — a lesson only ever needs a title) and fill in details later.
    title = models.CharField(max_length=255, blank=True, default='')
    description = models.TextField(blank=True, default='')
    due_days = models.PositiveIntegerField(default=7)  # days after enrollment
    submission_type = models.CharField(max_length=20, choices=SUBMISSION_TYPE_CHOICES, default='text')

    def __str__(self):
        return self.title


class LessonAssignmentSubmission(models.Model):
    assignment = models.ForeignKey(LessonAssignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lesson_assignment_submissions',
    )
    content = models.TextField(blank=True, default='')  # text/url/code submissions
    file = models.FileField(upload_to='lessons/assignment_submissions/', blank=True, null=True)
    grade = models.IntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True, default='')
    submitted_at = models.DateTimeField(auto_now_add=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['assignment', 'student']

    def __str__(self):
        return f"{self.student.username} — {self.assignment.title}"
