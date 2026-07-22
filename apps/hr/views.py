import calendar
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from rest_framework.parsers import MultiPartParser, FormParser

from apps.core.email import send_via_resend
from apps.rbac.mixins import RBACScopedMixin
from apps.companies.mixins import CompanyScopedMixin
from .models import (Attendance, Department, Employee, LeaveRequest, PaySlip,
                     Payroll, SalaryStructure, Shift,
                     PerformanceReview, EmployeeDocument, OnboardingChecklist, ExitManagement)
from .serializers import (AttendanceSerializer, DepartmentSerializer,
                          EmployeeSerializer, LeaveRequestSerializer,
                          PaySlipSerializer, PayrollSerializer,
                          SalaryStructureSerializer, ShiftSerializer,
                          PerformanceReviewSerializer, EmployeeDocumentSerializer,
                          OnboardingChecklistSerializer, ExitManagementSerializer)

# TEMPORARY: xerxez.com is not yet verified in Resend, so sends must use
# Resend's shared onboarding@resend.dev sender until domain verification completes.
FROM_EMAIL = 'onboarding@resend.dev'


def _send_leave_decision_email(leave):
    if not leave.employee.email:
        return
    approved = leave.status == 'approved'
    subject = f"Your {leave.get_type_display()} leave request has been {leave.status}"
    badge_bg, badge_color = ('#d1fae5', '#065f46') if approved else ('#fee2e2', '#991b1b')

    plain = f"""
Hi {leave.employee.full_name},

Your {leave.get_type_display()} leave request from {leave.from_date} to {leave.to_date} ({leave.days} day(s)) has been {leave.status}.
{f"Reason: {leave.rejection_reason}" if not approved and leave.rejection_reason else ""}

— XERXEZ HR
""".strip()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
  .wrap{{max-width:560px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;
         box-shadow:0 4px 32px rgba(0,0,0,.10)}}
  .hdr{{background:linear-gradient(135deg,#1a1208 0%,#0f0a05 100%);padding:36px 44px;text-align:center}}
  .hdr h1{{color:#C9883A;font-family:Georgia,serif;font-size:24px;margin:0 0 6px}}
  .hdr p{{color:rgba(255,255,255,.42);font-size:13px;margin:0}}
  .body{{padding:36px 44px}}
  .badge{{display:inline-block;padding:5px 16px;border-radius:100px;font-size:11px;
           font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:22px;
           background:{badge_bg};color:{badge_color}}}
  table{{width:100%;border-collapse:collapse}}
  tr:nth-child(even) td{{background:#fafaf8}}
  td{{padding:12px 14px;font-size:14px;color:#333;vertical-align:top;border-bottom:1px solid #f0ede8}}
  td:first-child{{width:38%;font-weight:700;color:#5a5650;font-size:11px;text-transform:uppercase;letter-spacing:.09em}}
  .msg{{background:#fafaf8;border-left:3px solid #ef4444;border-radius:0 8px 8px 0;
        padding:18px 20px;margin-top:22px;font-size:14px;line-height:1.72;color:#333}}
  .ftr{{background:#F8F7F4;border-top:1px solid #e8e4de;padding:18px 44px;
        text-align:center;font-size:12px;color:#9b9690}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><h1>XERXEZ</h1><p>Leave Request Update</p></div>
  <div class="body">
    <span class="badge">{leave.get_status_display()}</span>
    <table>
      <tr><td>Employee</td>   <td>{leave.employee.full_name}</td></tr>
      <tr><td>Leave Type</td> <td>{leave.get_type_display()}</td></tr>
      <tr><td>From</td>       <td>{leave.from_date}</td></tr>
      <tr><td>To</td>         <td>{leave.to_date}</td></tr>
      <tr><td>Total Days</td> <td>{leave.days}</td></tr>
    </table>
    {f'<div class="msg"><strong>Reason for rejection:</strong><br>{leave.rejection_reason}</div>' if not approved and leave.rejection_reason else ''}
  </div>
  <div class="ftr">XERXEZ HR &nbsp;·&nbsp; xerxez.com</div>
</div>
</body>
</html>"""

    send_via_resend(to=leave.employee.email, subject=subject, html=html, text=plain, from_email=FROM_EMAIL)


DEFAULT_ONBOARDING_TASKS = [
    'Email account created',
    'Laptop/equipment assigned',
    'Access cards issued',
    'HR documentation completed',
    'Team introduction done',
    'First week training completed',
]


class DepartmentViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Department.objects.select_related('head', 'manager').annotate(
        employee_count=Count('employees', distinct=True),
    ).all()
    serializer_class = DepartmentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code']


class EmployeeViewSet(RBACScopedMixin, viewsets.ModelViewSet):
    rbac_module = 'hr'
    queryset = Employee.objects.select_related('department', 'user').all()
    serializer_class = EmployeeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['full_name', 'email', 'code']
    filterset_fields = ['department', 'status']

    @action(detail=False, methods=['get'], url_path='linkable-users')
    def linkable_users(self, request):
        if not request.user.is_staff:
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
        User = get_user_model()
        users = User.objects.order_by('username').values('id', 'username', 'email', 'first_name', 'last_name')
        return Response(list(users))

    @action(detail=True, methods=['get', 'post'], url_path='documents',
            parser_classes=[MultiPartParser, FormParser])
    def documents(self, request, pk=None):
        employee = self.get_object()
        if request.method == 'POST':
            ser = EmployeeDocumentSerializer(data=request.data, context={'request': request})
            ser.is_valid(raise_exception=True)
            ser.save(employee=employee, company=employee.company)
            return Response(ser.data, status=status.HTTP_201_CREATED)
        qs = employee.documents.all()
        return Response(EmployeeDocumentSerializer(qs, many=True, context={'request': request}).data)

    @action(detail=True, methods=['get', 'post'], url_path='onboarding')
    def onboarding(self, request, pk=None):
        employee = self.get_object()
        if request.method == 'POST':
            # Seed the default 6-item checklist if none exists yet.
            if not employee.onboarding.exists():
                OnboardingChecklist.objects.bulk_create([
                    OnboardingChecklist(employee=employee, task=t, order=i, company=employee.company)
                    for i, t in enumerate(DEFAULT_ONBOARDING_TASKS)
                ])
        qs = employee.onboarding.all()
        return Response(OnboardingChecklistSerializer(qs, many=True).data)


class AttendanceViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Attendance.objects.select_related('employee').all()
    serializer_class = AttendanceSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['employee', 'date', 'status']
    ordering_fields = ['date']

    def _get_employee(self, request):
        try:
            return request.user.employee_profile
        except Exception:
            return None

    @action(detail=False, methods=['post'], url_path='clock-in')
    def clock_in(self, request):
        employee = self._get_employee(request)
        if not employee:
            return Response({'detail': 'No employee profile linked to your account.'}, status=status.HTTP_400_BAD_REQUEST)

        today = date.today()
        att, created = Attendance.objects.get_or_create(
            employee=employee, date=today,
            defaults={'check_in': timezone.now(), 'status': 'present', 'company': employee.company},
        )
        if not created:
            if att.check_in:
                return Response({'detail': 'Already clocked in today.'}, status=status.HTTP_400_BAD_REQUEST)
            att.check_in = timezone.now()
            att.status = 'present'
            att.save()
        return Response(AttendanceSerializer(att).data)

    @action(detail=False, methods=['post'], url_path='clock-out')
    def clock_out(self, request):
        employee = self._get_employee(request)
        if not employee:
            return Response({'detail': 'No employee profile linked.'}, status=status.HTTP_400_BAD_REQUEST)

        today = date.today()
        try:
            att = Attendance.objects.get(employee=employee, date=today)
        except Attendance.DoesNotExist:
            return Response({'detail': 'No clock-in record for today.'}, status=status.HTTP_400_BAD_REQUEST)

        if not att.check_in:
            return Response({'detail': 'Must clock in first.'}, status=status.HTTP_400_BAD_REQUEST)
        if att.check_out:
            return Response({'detail': 'Already clocked out today.'}, status=status.HTTP_400_BAD_REQUEST)

        att.check_out = timezone.now()
        delta = att.check_out - att.check_in
        att.hours = round(delta.total_seconds() / 3600, 2)

        # Auto-classify status
        cin = att.check_in
        late_threshold_hour, late_threshold_min = 9, 30
        is_late = (cin.hour > late_threshold_hour) or (cin.hour == late_threshold_hour and cin.minute > late_threshold_min)
        if float(att.hours) < 4:
            att.status = 'half_day'
        elif is_late:
            att.status = 'late'
        else:
            att.status = 'present'
        att.save()
        return Response(AttendanceSerializer(att).data)

    @action(detail=False, methods=['get'], url_path='today-status')
    def today_status(self, request):
        employee = self._get_employee(request)
        if not employee:
            return Response({'clocked_in': False, 'clocked_out': False})
        today = date.today()
        try:
            att = Attendance.objects.get(employee=employee, date=today)
            return Response({
                'clocked_in': bool(att.check_in),
                'clocked_out': bool(att.check_out),
                'check_in': att.check_in,
                'check_out': att.check_out,
                'hours': str(att.hours),
                'status': att.status,
            })
        except Attendance.DoesNotExist:
            return Response({'clocked_in': False, 'clocked_out': False})

    @action(detail=False, methods=['get'], url_path='my-records')
    def my_records(self, request):
        employee = self._get_employee(request)
        if not employee:
            return Response([])
        qs = Attendance.objects.filter(employee=employee).order_by('-date')
        return Response(AttendanceSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='report')
    def report(self, request):
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        qs = self.queryset
        if emp := request.query_params.get('employee'):
            qs = qs.filter(employee=emp)
        if date_from := request.query_params.get('date_from'):
            qs = qs.filter(date__gte=date_from)
        if date_to := request.query_params.get('date_to'):
            qs = qs.filter(date__lte=date_to)
        if att_status := request.query_params.get('status'):
            qs = qs.filter(status=att_status)
        return Response(AttendanceSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """GET /hr/attendance/summary/?employee_id=&month=&year= — per-employee monthly counts."""
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        qs = Attendance.objects.all()
        if emp := request.query_params.get('employee_id'):
            qs = qs.filter(employee_id=emp)
        if month:
            qs = qs.filter(date__month=int(month))
        if year:
            qs = qs.filter(date__year=int(year))

        buckets = {}
        for att in qs.select_related('employee'):
            b = buckets.setdefault(att.employee_id, {
                'employee_id': att.employee_id,
                'employee_name': att.employee.full_name,
                'present': 0, 'absent': 0, 'late': 0, 'half_day': 0, 'total': 0,
            })
            key = att.status if att.status in ('present', 'absent', 'late', 'half_day') else 'present'
            b[key] += 1
            b['total'] += 1
        return Response(list(buckets.values()))


LEAVE_ANNUAL_ALLOWANCE = {
    'annual': 21,
    'sick': 12,
    'emergency': 5,
    # unpaid / maternity / paternity / other are uncapped — handled case-by-case, not a pooled allowance.
}


class LeaveRequestViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.select_related('employee', 'decided_by').all()
    serializer_class = LeaveRequestSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['employee', 'status', 'type']
    search_fields = ['employee__full_name', 'employee__code']

    def get_queryset(self):
        qs = super().get_queryset()
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(from_date__gte=date_from)
        if date_to:
            qs = qs.filter(to_date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        employee = serializer.validated_data.get('employee')
        serializer.save(company=employee.company if employee else None)

    @action(detail=True, methods=['patch'], url_path='approve')
    def approve(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        leave = self.get_object()
        action_val = request.data.get('action', 'approved')
        if action_val not in ('approved', 'rejected'):
            return Response({'detail': 'action must be "approved" or "rejected".'}, status=status.HTTP_400_BAD_REQUEST)
        leave.status = action_val
        leave.decided_by = request.user
        leave.decided_at = timezone.now()
        leave.rejection_reason = request.data.get('rejection_reason', '') if action_val == 'rejected' else ''
        leave.save()
        _send_leave_decision_email(leave)
        return Response(LeaveRequestSerializer(leave).data)

    @action(detail=False, methods=['get'], url_path='my-leaves')
    def my_leaves(self, request):
        try:
            employee = request.user.employee_profile
        except Exception:
            return Response([])
        qs = LeaveRequest.objects.filter(employee=employee).order_by('-created_at')
        return Response(LeaveRequestSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='balance')
    def balance(self, request):
        """GET /hr/leave-requests/balance/?employee=<id>&leave_type=<type> — this calendar
        year's allowance/used/remaining for one employee + leave type, from approved requests."""
        employee_id = request.query_params.get('employee')
        leave_type = request.query_params.get('leave_type') or request.query_params.get('type')
        if not employee_id or not leave_type:
            return Response({'detail': 'employee and leave_type query params are required.'}, status=status.HTTP_400_BAD_REQUEST)

        year = timezone.now().year
        used = LeaveRequest.objects.filter(
            employee_id=employee_id, type=leave_type, status='approved', from_date__year=year,
        ).aggregate(total=Sum('days'))['total'] or 0
        used = float(used)

        allowance = LEAVE_ANNUAL_ALLOWANCE.get(leave_type)
        if allowance is None:
            return Response({'leave_type': leave_type, 'unlimited': True, 'allowance': None, 'used': used, 'remaining': None})
        return Response({'leave_type': leave_type, 'unlimited': False, 'allowance': allowance, 'used': used, 'remaining': max(allowance - used, 0)})


class ShiftViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Shift.objects.prefetch_related('employees').all()
    serializer_class = ShiftSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


class SalaryStructureViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = SalaryStructure.objects.select_related('employee').all()
    serializer_class = SalaryStructureSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee']

    def perform_create(self, serializer):
        employee = serializer.validated_data.get('employee')
        serializer.save(company=employee.company if employee else None)


class PayrollViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Payroll.objects.select_related('employee', 'generated_by').all()
    serializer_class = PayrollSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['employee', 'month', 'year', 'status']
    ordering_fields = ['year', 'month']

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        month = request.data.get('month')
        year = request.data.get('year')
        if not month or not year:
            return Response({'detail': 'month and year are required.'}, status=status.HTTP_400_BAD_REQUEST)

        month, year = int(month), int(year)
        _, working_days = calendar.monthrange(year, month)

        PAYROLL_FIELDS = ['working_days', 'present_days', 'basic', 'allowances', 'deductions', 'gross', 'net_salary', 'status', 'generated_by']

        employees = list(Employee.objects.filter(status='active').select_related('salary_structure'))
        existing_by_employee = {
            p.employee_id: p
            for p in Payroll.objects.filter(month=month, year=year, employee__in=employees)
        }

        to_create, to_update = [], []
        for emp in employees:
            try:
                ss = emp.salary_structure
            except SalaryStructure.DoesNotExist:
                continue

            present_days = Attendance.objects.filter(
                employee=emp, date__year=year, date__month=month,
                status__in=['present', 'late'],
            ).count()
            half_days = Attendance.objects.filter(
                employee=emp, date__year=year, date__month=month,
                status='half_day',
            ).count()

            effective_days = present_days + (half_days * 0.5)
            daily_rate = float(ss.basic_salary) / working_days if working_days else 0
            basic_earned = round(daily_rate * effective_days, 2)

            total_allowances = sum(float(v) for v in ss.allowances.values())
            total_deductions = sum(float(v) for v in ss.deductions.values())
            gross = basic_earned + total_allowances
            net = gross - total_deductions

            fields = {
                'working_days': working_days,
                'present_days': int(effective_days),
                'basic': basic_earned,
                'allowances': total_allowances,
                'deductions': total_deductions,
                'gross': gross,
                'net_salary': net,
                'status': 'draft',
                'generated_by': request.user,
            }

            payroll = existing_by_employee.get(emp.id)
            if payroll is not None:
                for field, value in fields.items():
                    setattr(payroll, field, value)
                to_update.append(payroll)
            else:
                to_create.append(Payroll(employee=emp, month=month, year=year, company=emp.company, **fields))

        with transaction.atomic():
            if to_create:
                Payroll.objects.bulk_create(to_create, batch_size=500)
            if to_update:
                Payroll.objects.bulk_update(to_update, PAYROLL_FIELDS, batch_size=500)

            all_payrolls = to_create + to_update
            payrolls_without_payslip = set(
                Payroll.objects.filter(pk__in=[p.pk for p in all_payrolls], payslip__isnull=True)
                .values_list('pk', flat=True)
            )
            PaySlip.objects.bulk_create([
                PaySlip(payroll=p, company=p.company) for p in all_payrolls if p.pk in payrolls_without_payslip
            ], batch_size=500)

        created_payrolls = [PayrollSerializer(p).data for p in all_payrolls]
        return Response({'generated': len(created_payrolls), 'payrolls': created_payrolls})

    @action(detail=True, methods=['patch'], url_path='approve')
    def approve(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        payroll = self.get_object()
        payroll.status = 'approved'
        payroll.save()
        return Response(PayrollSerializer(payroll).data)

    @action(detail=True, methods=['patch'], url_path='mark-paid')
    def mark_paid(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        payroll = self.get_object()
        payroll.status = 'paid'
        payroll.paid_at = timezone.now()
        payroll.save()
        return Response(PayrollSerializer(payroll).data)

    @action(detail=False, methods=['get'], url_path='my-payslips')
    def my_payslips(self, request):
        try:
            employee = request.user.employee_profile
        except Exception:
            return Response([])
        qs = Payroll.objects.filter(employee=employee).order_by('-year', '-month')
        return Response(PayrollSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'], url_path='payslip')
    def payslip(self, request, pk=None):
        """GET /hr/payroll/{id}/payslip/ — full payslip detail for the modal/download."""
        payroll = self.get_object()
        PaySlip.objects.get_or_create(payroll=payroll, defaults={'company': payroll.company})
        return Response(PayrollSerializer(payroll).data)

    @action(detail=False, methods=['get'], url_path='report')
    def report(self, request):
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        qs = self.queryset
        if month := request.query_params.get('month'):
            qs = qs.filter(month=month)
        if year := request.query_params.get('year'):
            qs = qs.filter(year=year)
        return Response(PayrollSerializer(qs, many=True).data)


class PaySlipViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PaySlip.objects.select_related('payroll__employee').all()
    serializer_class = PaySlipSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['payroll__employee', 'payroll__month', 'payroll__year']


class PerformanceReviewViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = PerformanceReview.objects.select_related('employee', 'reviewer').all()
    serializer_class = PerformanceReviewSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'rating']

    def perform_create(self, serializer):
        employee = serializer.validated_data.get('employee')
        serializer.save(reviewer=self.request.user, company=employee.company if employee else None)


class EmployeeDocumentViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = EmployeeDocument.objects.select_related('employee').all()
    serializer_class = EmployeeDocumentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'doc_type']


class OnboardingChecklistViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = OnboardingChecklist.objects.select_related('employee').all()
    serializer_class = OnboardingChecklistSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'completed']

    @action(detail=True, methods=['patch'], url_path='toggle')
    def toggle(self, request, pk=None):
        item = self.get_object()
        item.completed = not item.completed
        item.completed_at = timezone.now() if item.completed else None
        item.save()
        return Response(OnboardingChecklistSerializer(item).data)


class ExitManagementViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = ExitManagement.objects.select_related('employee').all()
    serializer_class = ExitManagementSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'reason', 'settlement_paid']

    def perform_create(self, serializer):
        employee = serializer.validated_data.get('employee')
        serializer.save(company=employee.company if employee else None)

    @action(detail=True, methods=['patch'], url_path='mark-interview-done')
    def mark_interview_done(self, request, pk=None):
        rec = self.get_object()
        rec.exit_interview_done = True
        rec.save()
        return Response(ExitManagementSerializer(rec).data)

    @action(detail=True, methods=['patch'], url_path='mark-settlement-paid')
    def mark_settlement_paid(self, request, pk=None):
        rec = self.get_object()
        rec.settlement_paid = True
        amount = request.data.get('final_settlement_amount')
        if amount is not None:
            rec.final_settlement_amount = amount
        rec.save()
        return Response(ExitManagementSerializer(rec).data)
