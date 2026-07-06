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
