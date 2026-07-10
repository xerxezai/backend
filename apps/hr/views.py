import calendar
from datetime import date

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from rest_framework.parsers import MultiPartParser, FormParser

from .models import (Attendance, Department, Employee, LeaveRequest, PaySlip,
                     Payroll, SalaryStructure, Shift,
                     PerformanceReview, EmployeeDocument, OnboardingChecklist, ExitManagement)
from .serializers import (AttendanceSerializer, DepartmentSerializer,
                          EmployeeSerializer, LeaveRequestSerializer,
                          PaySlipSerializer, PayrollSerializer,
                          SalaryStructureSerializer, ShiftSerializer,
                          PerformanceReviewSerializer, EmployeeDocumentSerializer,
                          OnboardingChecklistSerializer, ExitManagementSerializer)

DEFAULT_ONBOARDING_TASKS = [
    'Email account created',
    'Laptop/equipment assigned',
    'Access cards issued',
    'HR documentation completed',
    'Team introduction done',
    'First week training completed',
]


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code']


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related('department', 'user').all()
    serializer_class = EmployeeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['full_name', 'email', 'code']
    filterset_fields = ['department', 'status']

    @action(detail=True, methods=['get', 'post'], url_path='documents',
            parser_classes=[MultiPartParser, FormParser])
    def documents(self, request, pk=None):
        employee = self.get_object()
        if request.method == 'POST':
            ser = EmployeeDocumentSerializer(data=request.data, context={'request': request})
            ser.is_valid(raise_exception=True)
            ser.save(employee=employee)
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
                    OnboardingChecklist(employee=employee, task=t, order=i)
                    for i, t in enumerate(DEFAULT_ONBOARDING_TASKS)
                ])
        qs = employee.onboarding.all()
        return Response(OnboardingChecklistSerializer(qs, many=True).data)


class AttendanceViewSet(viewsets.ModelViewSet):
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
            defaults={'check_in': timezone.now(), 'status': 'present'},
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


class LeaveRequestViewSet(viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.select_related('employee', 'decided_by').all()
    serializer_class = LeaveRequestSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'status', 'type']

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
        leave.save()
        return Response(LeaveRequestSerializer(leave).data)

    @action(detail=False, methods=['get'], url_path='my-leaves')
    def my_leaves(self, request):
        try:
            employee = request.user.employee_profile
        except Exception:
            return Response([])
        qs = LeaveRequest.objects.filter(employee=employee).order_by('-created_at')
        return Response(LeaveRequestSerializer(qs, many=True).data)


class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.prefetch_related('employees').all()
    serializer_class = ShiftSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


class SalaryStructureViewSet(viewsets.ModelViewSet):
    queryset = SalaryStructure.objects.select_related('employee').all()
    serializer_class = SalaryStructureSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee']


class PayrollViewSet(viewsets.ModelViewSet):
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

        created_payrolls = []
        for emp in Employee.objects.filter(status='active'):
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

            payroll, _ = Payroll.objects.update_or_create(
                employee=emp, month=month, year=year,
                defaults={
                    'working_days': working_days,
                    'present_days': int(effective_days),
                    'basic': basic_earned,
                    'allowances': total_allowances,
                    'deductions': total_deductions,
                    'gross': gross,
                    'net_salary': net,
                    'status': 'draft',
                    'generated_by': request.user,
                },
            )
            PaySlip.objects.get_or_create(payroll=payroll)
            created_payrolls.append(PayrollSerializer(payroll).data)

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
        PaySlip.objects.get_or_create(payroll=payroll)
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


class PaySlipViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PaySlip.objects.select_related('payroll__employee').all()
    serializer_class = PaySlipSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['payroll__employee', 'payroll__month', 'payroll__year']


class PerformanceReviewViewSet(viewsets.ModelViewSet):
    queryset = PerformanceReview.objects.select_related('employee', 'reviewer').all()
    serializer_class = PerformanceReviewSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'rating']

    def perform_create(self, serializer):
        serializer.save(reviewer=self.request.user)


class EmployeeDocumentViewSet(viewsets.ModelViewSet):
    queryset = EmployeeDocument.objects.select_related('employee').all()
    serializer_class = EmployeeDocumentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'doc_type']


class OnboardingChecklistViewSet(viewsets.ModelViewSet):
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


class ExitManagementViewSet(viewsets.ModelViewSet):
    queryset = ExitManagement.objects.select_related('employee').all()
    serializer_class = ExitManagementSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'reason', 'settlement_paid']

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
