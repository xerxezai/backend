"""HR models: departments, employees, attendance, leave, shifts, payroll."""
from django.conf import settings
from django.db import models


class Department(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120, unique=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_departments')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Employee(models.Model):
    STATUS = [
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('resigned', 'Resigned'),
        ('terminated', 'Terminated'),
    ]
    code = models.CharField(max_length=20, unique=True, help_text='e.g. EMP-0001')
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='employee_profile')
    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name='employees')
    designation = models.CharField(max_length=120, blank=True)
    joined_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='active')
    salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return f'{self.code} - {self.full_name}'


class Attendance(models.Model):
    ATTENDANCE_STATUS = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('half_day', 'Half Day'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    # Added additively — existing rows default to blank (backfilled to 'present' via migration default)
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS, default='present', blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-date']
        unique_together = [('employee', 'date')]

    def __str__(self):
        return f'{self.employee} {self.date}'


class LeaveRequest(models.Model):
    TYPE = [
        ('annual', 'Annual'),
        ('sick', 'Sick'),
        ('unpaid', 'Unpaid'),
        ('maternity', 'Maternity'),
        ('paternity', 'Paternity'),
        ('other', 'Other'),
    ]
    STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    type = models.CharField(max_length=20, choices=TYPE, default='annual')
    from_date = models.DateField()
    to_date = models.DateField()
    days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='leave_decisions')
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Shift(models.Model):
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    employees = models.ManyToManyField(Employee, blank=True, related_name='shifts')

    def __str__(self):
        return self.name


class SalaryStructure(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='salary_structure')
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances = models.JSONField(default=dict, blank=True)
    deductions = models.JSONField(default=dict, blank=True)
    effective_date = models.DateField()

    def __str__(self):
        return f'{self.employee} — Salary Structure'


class Payroll(models.Model):
    STATUS = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payrolls')
    month = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()
    working_days = models.PositiveSmallIntegerField(default=0)
    present_days = models.PositiveSmallIntegerField(default=0)
    basic = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS, default='draft')
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='generated_payrolls')
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(fields=['employee', 'month', 'year'], name='unique_payroll_per_employee_month')
        ]

    def __str__(self):
        return f'{self.employee} {self.month}/{self.year}'


class PaySlip(models.Model):
    payroll = models.OneToOneField(Payroll, on_delete=models.CASCADE, related_name='payslip')
    pdf_ref = models.CharField(max_length=255, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'PaySlip — {self.payroll}'


# ─────────────────────────────────────────────────────────────────────────────
# Added HR features: Performance, Documents, Onboarding, Exit
# (Attendance & Payroll already exist above — reused, not duplicated.)
# ─────────────────────────────────────────────────────────────────────────────

class PerformanceReview(models.Model):
    RATING_CHOICES = [(1, 'Poor'), (2, 'Below Average'), (3, 'Average'), (4, 'Good'), (5, 'Excellent')]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    period = models.CharField(max_length=50)
    rating = models.IntegerField(choices=RATING_CHOICES)
    goals_achieved = models.TextField(blank=True)
    areas_improvement = models.TextField(blank=True)
    comments = models.TextField(blank=True)
    review_date = models.DateField(auto_now_add=True)

    class Meta:
        db_table = 'hr_performance_review'
        ordering = ['-review_date']

    def __str__(self):
        return f'{self.employee} — {self.period} ({self.rating}/5)'


class EmployeeDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ('offer_letter', 'Offer Letter'), ('id_proof', 'ID Proof'),
        ('contract', 'Contract'), ('certificate', 'Certificate'), ('other', 'Other'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES)
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='hr/documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hr_employee_document'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.employee} — {self.name}'


class OnboardingChecklist(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='onboarding')
    task = models.CharField(max_length=200)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        db_table = 'hr_onboarding_checklist'
        ordering = ['order']

    def __str__(self):
        return f'{self.employee} — {self.task}'


class ExitManagement(models.Model):
    REASON_CHOICES = [
        ('resignation', 'Resignation'), ('termination', 'Termination'),
        ('retirement', 'Retirement'), ('contract_end', 'Contract End'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='exit')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    last_working_day = models.DateField()
    notice_period_days = models.IntegerField(default=30)
    exit_interview_done = models.BooleanField(default=False)
    final_settlement_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    settlement_paid = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hr_exit_management'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.employee} — {self.get_reason_display()}'
