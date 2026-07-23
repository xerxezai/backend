"""HR models: departments, employees, attendance, leave, shifts, payroll."""
from datetime import date
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.validators import validate_phone_with_country_code


class Department(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_departments')
    head = models.ForeignKey('Employee', null=True, blank=True, on_delete=models.SET_NULL, related_name='headed_departments')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    color = models.CharField(max_length=20, default='#c8a84b')
    icon = models.CharField(max_length=50, default='briefcase')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Employee(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    STATUS = [
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('resigned', 'Resigned'),
        ('terminated', 'Terminated'),
    ]
    GENDER = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say'),
    ]
    CURRENCY = [
        ('INR', 'INR'),
        ('AED', 'AED'),
        ('USD', 'USD'),
    ]
    code = models.CharField(max_length=20, unique=True, help_text='e.g. EMP-0001')
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='employee_profile')
    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True, validators=[validate_phone_with_country_code])
    profile_photo = models.ImageField(upload_to='hr/employees/photos/', null=True, blank=True)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name='employees')
    designation = models.CharField(max_length=120, blank=True)
    joined_on = models.DateField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER, blank=True)
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=40, blank=True, validators=[validate_phone_with_country_code])
    status = models.CharField(max_length=20, choices=STATUS, default='active')
    salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    salary_currency = models.CharField(max_length=3, choices=CURRENCY, default='INR')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_employees',
        help_text='Who created this record — drives RBAC data-level filtering for Regular User/Read Only roles.',
    )

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return f'{self.code} - {self.full_name}'


class Attendance(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
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
    is_manual = models.BooleanField(default=False, help_text='True when an admin added/edited this record by hand rather than the employee clocking in/out.')

    class Meta:
        ordering = ['-date']
        unique_together = [('employee', 'date')]

    def __str__(self):
        return f'{self.employee} {self.date}'


class LeaveRequest(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    TYPE = [
        ('annual', 'Annual'),
        ('sick', 'Sick'),
        ('emergency', 'Emergency'),
        ('maternity', 'Maternity'),
        ('paternity', 'Paternity'),
        ('unpaid', 'Unpaid'),
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
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class LeavePolicy(models.Model):
    """Per-company, per-leave-type policy: how many days are allowed per year, and whether
    unused days carry forward. Drives LeaveRequestViewSet.balance() instead of a hardcoded
    allowance — see apps.hr.views.LEAVE_ANNUAL_ALLOWANCE (removed)."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='leave_policies')
    leave_type = models.CharField(max_length=20, choices=LeaveRequest.TYPE)
    days_allowed = models.IntegerField(default=0)
    carry_forward = models.BooleanField(default=False)
    max_carry_forward_days = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hr_leavepolicy'
        unique_together = ['company', 'leave_type']
        ordering = ['leave_type']

    def __str__(self):
        return f'{self.company} — {self.get_leave_type_display()}'


# Seeded onto every new company (CompanyListView.post) and backfilled onto any company that
# predates this feature (see management command backfill_leave_policies) — Company Admin can
# then edit these to match their actual policy. Unpaid Leave is intentionally uncapped (see
# LeaveRequestViewSet.balance): its days_allowed=0 row exists only so it's visible/editable
# on the Leave Policy page, it is never used to cap a balance.
DEFAULT_LEAVE_POLICIES = [
    ('annual', 21), ('sick', 10), ('emergency', 5),
    ('maternity', 90), ('paternity', 7), ('unpaid', 0),
]


def create_default_leave_policies(company):
    for leave_type, days in DEFAULT_LEAVE_POLICIES:
        LeavePolicy.objects.get_or_create(company=company, leave_type=leave_type, defaults={'days_allowed': days})


class Shift(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    SHIFT_TYPES = [
        ('Morning', 'Morning'),
        ('Evening', 'Evening'),
        ('Night', 'Night'),
        ('Rotational', 'Rotational'),
    ]
    name = models.CharField(max_length=100)
    shift_type = models.CharField(max_length=20, choices=SHIFT_TYPES, default='Morning')
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_duration = models.IntegerField(default=30, help_text='Break duration in minutes')
    grace_period = models.IntegerField(default=10, help_text='Minutes late allowed before marked late')
    working_days = models.JSONField(default=list, blank=True, help_text="e.g. ['Monday', 'Tuesday', ...]")
    color = models.CharField(max_length=20, default='#c8a84b')
    is_active = models.BooleanField(default=True)
    employees = models.ManyToManyField(Employee, blank=True, related_name='shifts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SalaryStructure(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='salary_structure')
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances = models.JSONField(default=dict, blank=True)
    deductions = models.JSONField(default=dict, blank=True)
    effective_date = models.DateField()

    def __str__(self):
        return f'{self.employee} — Salary Structure'


class Payroll(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
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
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
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
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
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
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    # Old values (id_proof/contract/certificate) stay valid on already-stored rows even
    # though they're no longer offered in the dropdown — Django only validates `choices`
    # on serializer/form input, not on read, so nothing breaks for existing documents.
    DOC_TYPE_CHOICES = [
        ('aadhar_card', 'Aadhaar Card'),
        ('pan_card', 'PAN Card'),
        ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
        ('emirates_id', 'Emirates ID'),
        ('visa', 'Visa'),
        ('employment_contract', 'Employment Contract'),
        ('offer_letter', 'Offer Letter'),
        ('appointment_letter', 'Appointment Letter'),
        ('experience_certificate', 'Experience Letter'),
        ('relieving_letter', 'Relieving Letter'),
        ('educational_certificate', 'Educational Certificate'),
        ('degree_certificate', 'Degree Certificate'),
        ('marksheet', 'Marksheet'),
        ('medical_certificate', 'Medical Certificate'),
        ('insurance', 'Insurance Document'),
        ('bank_account_details', 'Bank Account Details'),
        ('cancelled_cheque', 'Cancelled Cheque'),
        ('salary_slip', 'Salary Slip'),
        ('background_verification', 'Background Verification'),
        ('nda', 'NDA'),
        ('other', 'Other'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='employee_documents/')
    document_number = models.CharField(max_length=100, blank=True, help_text='Passport number, visa number, etc.')
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='uploaded_hr_documents',
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='verified_hr_documents',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    # Not part of the original spec — tracks whether the "expiring soon" email (see
    # apps.hr.views._send_document_expiring_email) has already gone out for this document,
    # so re-saving it (e.g. an admin editing notes) doesn't re-send the same alert.
    expiry_notified = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hr_employee_document'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.employee} — {self.name}'


class OnboardingChecklist(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    CATEGORY_CHOICES = [
        ('pre_joining', 'Pre-Joining'),
        ('day_1', 'Day 1'),
        ('first_week', 'First Week'),
        ('first_month', 'First Month'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='onboarding')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='pre_joining')
    task = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_onboarding_tasks',
    )
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    # Kept for backward compatibility with existing filters/consumers — `status` is now the
    # primary field; save() keeps these in sync with it automatically.
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Prevents send_onboarding_reminders from re-emailing the assignee every time it runs.
    reminder_sent = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    class Meta:
        db_table = 'hr_onboarding_checklist'
        ordering = ['order']

    def __str__(self):
        return f'{self.employee} — {self.task}'

    def save(self, *args, **kwargs):
        if self.status == 'completed' and not self.completed:
            self.completed = True
            if not self.completed_at:
                self.completed_at = timezone.now()
        elif self.status != 'completed' and self.completed:
            self.completed = False
            self.completed_at = None
        super().save(*args, **kwargs)


class ExitManagement(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
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


# ─────────────────────────────────────────────────────────────────────────────
# New: Holidays, Overtime — everything else in this file already existed.
# ─────────────────────────────────────────────────────────────────────────────

class Holiday(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    TYPE_CHOICES = [
        ('public', 'Public'),
        ('company', 'Company'),
        ('optional', 'Optional'),
    ]
    name = models.CharField(max_length=255)
    date = models.DateField()
    holiday_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='public')
    description = models.TextField(blank=True)
    is_recurring = models.BooleanField(default=False, help_text='Automatically applies every year on this same month/day.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hr_holiday'
        ordering = ['date']

    def effective_date_for_year(self, year):
        """This holiday's month/day projected onto `year` — Feb 29 falls back to Feb 28
        in a non-leap year rather than raising."""
        try:
            return self.date.replace(year=year)
        except ValueError:
            return date(year, 2, 28)

    def next_occurrence(self, today=None):
        """The next date this holiday falls on. Non-recurring holidays just occur once,
        on their stored date (which may already be in the past). Recurring holidays project
        onto the current year, rolling over to next year once that date has passed."""
        today = today or date.today()
        if not self.is_recurring:
            return self.date
        this_year = self.effective_date_for_year(today.year)
        return this_year if this_year >= today else self.effective_date_for_year(today.year + 1)

    def __str__(self):
        return f'{self.name} — {self.date}'


class Overtime(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    RATE_CHOICES = [('1.5x', '1.5x'), ('2x', '2x'), ('2.5x', '2.5x')]
    STATUS_CHOICES = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='overtime_entries')
    date = models.DateField()
    extra_hours = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField()
    rate = models.CharField(max_length=10, choices=RATE_CHOICES, default='1.5x')
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Overtime payment amount, entered manually by the admin (not auto-calculated).',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_overtime')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hr_overtime'
        ordering = ['-date']

    def __str__(self):
        return f'{self.employee} — {self.date} ({self.extra_hours}h)'
