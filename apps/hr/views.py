import calendar
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
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
from apps.rbac.permissions import ReadOnlyOrHigher
from apps.rbac.utils import get_user_role
from apps.companies.mixins import CompanyScopedMixin
from .models import (Attendance, Department, Employee, LeaveRequest, LeavePolicy, PaySlip,
                     Payroll, SalaryStructure, Shift,
                     PerformanceReview, EmployeeDocument, OnboardingChecklist, ExitManagement,
                     Holiday, Overtime)
from .serializers import (AttendanceSerializer, DepartmentSerializer,
                          EmployeeSerializer, LeaveRequestSerializer, LeavePolicySerializer,
                          PaySlipSerializer, PayrollSerializer,
                          SalaryStructureSerializer, ShiftSerializer,
                          PerformanceReviewSerializer, EmployeeDocumentSerializer,
                          OnboardingChecklistSerializer, ExitManagementSerializer,
                          HolidaySerializer, OvertimeSerializer)

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


DOCUMENT_EXPIRY_NOTIFY_EMAIL = 'xerxez.in@gmail.com'
DOCUMENT_EXPIRY_NOTIFY_DAYS = 7


def _hr_recipient_emails(company):
    """Who 'notify HR' actually means for a given company: its Company Admin(s) and HR
    Manager(s) (module_admin on 'hr'), not a single hardcoded inbox — this system is
    multi-tenant, so different companies have different HR staff. Falls back to the shared
    monitoring address if a company has nobody in either role yet (or has no company at all),
    so an alert is never silently dropped."""
    if not company:
        return [DOCUMENT_EXPIRY_NOTIFY_EMAIL]
    from apps.companies.models import CompanyUser
    from apps.rbac.models import UserModuleAccess

    admin_user_ids = set(
        CompanyUser.objects.filter(company=company, is_active=True, role='company_admin').values_list('user_id', flat=True),
    )
    hr_manager_user_ids = set(
        UserModuleAccess.objects.filter(
            module__name='hr', role='module_admin', is_active=True,
            user__company_memberships__company=company, user__company_memberships__is_active=True,
        ).values_list('user_id', flat=True),
    )
    User = get_user_model()
    emails = list(
        User.objects.filter(id__in=admin_user_ids | hr_manager_user_ids).exclude(email='').values_list('email', flat=True),
    )
    return emails or [DOCUMENT_EXPIRY_NOTIFY_EMAIL]


def _send_document_expiring_email(document):
    days = (document.expiry_date - date.today()).days
    subject = f"Document Expiring Soon — {document.employee.full_name} — {document.get_doc_type_display()}"
    recipients = _hr_recipient_emails(document.company)

    plain = f"""
Document {document.name} for employee {document.employee.full_name} expires on {document.expiry_date.strftime('%d %b %Y')} — {days} day(s) remaining.

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
           background:#fef3c7;color:#92400e}}
  table{{width:100%;border-collapse:collapse}}
  tr:nth-child(even) td{{background:#fafaf8}}
  td{{padding:12px 14px;font-size:14px;color:#333;vertical-align:top;border-bottom:1px solid #f0ede8}}
  td:first-child{{width:38%;font-weight:700;color:#5a5650;font-size:11px;text-transform:uppercase;letter-spacing:.09em}}
  .ftr{{background:#F8F7F4;border-top:1px solid #e8e4de;padding:18px 44px;
        text-align:center;font-size:12px;color:#9b9690}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><h1>XERXEZ</h1><p>Document Expiry Alert</p></div>
  <div class="body">
    <span class="badge">Expiring in {days} day(s)</span>
    <table>
      <tr><td>Employee</td>      <td>{document.employee.full_name}</td></tr>
      <tr><td>Document</td>      <td>{document.name}</td></tr>
      <tr><td>Type</td>          <td>{document.get_doc_type_display()}</td></tr>
      <tr><td>Expiry Date</td>   <td>{document.expiry_date.strftime('%d %b %Y')}</td></tr>
    </table>
  </div>
  <div class="ftr">XERXEZ HR &nbsp;·&nbsp; xerxez.com</div>
</div>
</body>
</html>"""

    send_via_resend(to=recipients, subject=subject, html=html, text=plain, from_email=FROM_EMAIL)


def _maybe_notify_document_expiring(document):
    """Sends the 'expiring soon' alert to HR (the company's Company Admin/HR Manager, see
    _hr_recipient_emails) the moment a document is saved with an expiry date that already
    falls within DOCUMENT_EXPIRY_NOTIFY_DAYS (covers uploading/editing a document that's
    already close to expiry). `expiry_notified` prevents re-sending on every later edit.
    A document that drifts into that window purely by the calendar moving forward (nobody
    re-saves it) needs a scheduled check instead — see the check_expiring_documents
    management command."""
    if document.expiry_notified or not document.expiry_date:
        return
    days = (document.expiry_date - date.today()).days
    if 0 <= days <= DOCUMENT_EXPIRY_NOTIFY_DAYS:
        _send_document_expiring_email(document)
        document.expiry_notified = True
        document.save(update_fields=['expiry_notified'])


def _is_hr_privileged(user):
    """Super Admin / Admin (Django is_staff or is_superuser) / Company Admin / HR Manager
    (RBAC module_admin scoped to the 'hr' module) — the roles that see and manage every
    employee's attendance, leave and payroll data. Everyone else only sees records for their
    own linked Employee.

    Company Admin is checked via get_user_role(user) with NO module argument (their highest
    role across *any* module) rather than get_user_role(user, 'hr') — a Company Admin's
    authority spans every module and was never meant to depend on whether a UserModuleAccess
    row for 'hr' specifically exists. That row can go missing (an Edit Access edit that didn't
    re-include 'hr', or any account whose per-module grants are simply incomplete), which
    silently downgraded a real Company Admin to "sees only their own record" everywhere in
    this file. Same reasoning apps.rbac.mixins.RBACScopedMixin.rbac_scope() already documents
    for the identical check.

    HR Manager (module_admin) stays scoped to the 'hr' module specifically — that distinction
    is meaningful (someone can be module_admin for crm without being an HR Manager) — and is
    deliberately NOT scoped down to "records they created" the way
    apps.rbac.utils.filter_queryset_by_role treats module_admin for other modules — an HR
    Manager needs company-wide HR visibility, so this is a bespoke check rather than a reuse
    of RBACScopedMixin."""
    if user.is_staff or user.is_superuser:
        return True
    if get_user_role(user) == 'company_admin':
        return True
    return get_user_role(user, 'hr') in ('super_admin', 'module_admin')


def _is_super_or_company_admin(user):
    """Stricter bar than _is_hr_privileged: Super Admin / Company Admin only, excluding HR
    Manager (module_admin on 'hr'). Used to gate deleting HR records (overtime entries, leave
    requests) — HR Manager can approve/reject those but not delete them; regular employees
    can't delete at all."""
    if user.is_staff or user.is_superuser:
        return True
    return get_user_role(user) == 'company_admin'


def _own_employee_or_none(request):
    try:
        return request.user.employee_profile
    except Exception:
        return None


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
    permission_classes = [IsAuthenticated, ReadOnlyOrHigher]
    module_name = 'hr'
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

    def get_queryset(self):
        # Bespoke override instead of RBACScopedMixin's default rbac_scope(): that scopes
        # module_admin/regular_user/read_only down to rows they personally *created*
        # (rbac_user_field='created_by'), which doesn't fit Employee — a regular employee
        # didn't create their own Employee record (an admin did), so the default would leave
        # them seeing nobody, including themselves. Regular users get their own record only
        # (via the `user` link); Super Admin/Company Admin/HR Manager keep full company-wide
        # visibility, same tenant boundary RBACScopedMixin would have applied.
        from apps.companies.utils import resolve_company, get_company_queryset
        qs = self.queryset.all()
        company, is_platform_admin = resolve_company(self.request)
        qs = get_company_queryset(qs, company, is_platform_admin, 'company')
        if is_platform_admin or _is_hr_privileged(self.request.user):
            return qs
        return qs.filter(user=self.request.user)

    def _require_privileged(self):
        if not _is_hr_privileged(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Admin only.')

    @staticmethod
    def _raise_friendly_integrity_error(exc):
        # Belt-and-suspenders on top of the serializer's UniqueValidator on `code` (see
        # EmployeeSerializer) — a genuine race between two near-simultaneous saves (e.g. a
        # double-click on Save, or two admins saving at once) can still slip past that
        # pre-check and only fail at the DB insert. Never let that reach the client as a raw
        # 500 — translate it into the same clean validation-error shape as everything else.
        from rest_framework.exceptions import ValidationError
        msg = str(exc).lower()
        if 'hr_employee_code_key' in msg or ('unique' in msg and 'code' in msg):
            raise ValidationError({'code': 'An employee with this code already exists — please try saving again.'})
        if 'user_id' in msg or ('unique' in msg and 'user' in msg):
            raise ValidationError({'user': 'This user account is already linked to an employee profile.'})
        raise ValidationError({'detail': 'Could not save this employee — a record with matching details already exists.'})

    def perform_create(self, serializer):
        self._require_privileged()
        # Refuse to silently create an Employee with no company — that row would be
        # invisible to every company-scoped query afterwards (the exact bug that let
        # setup_admin_employees and `link_employee_user --create` produce orphaned records
        # for Danish/Tanzeem and any manually-linked account; see backfill_employee_company
        # for the one-time repair of rows already created that way). A platform admin
        # (super_admin, no company selected in the Company Switcher) is exempt — "no
        # company" genuinely means "not scoped to one yet" for them, not a resolution failure.
        from apps.companies.utils import resolve_company
        company, is_platform_admin = resolve_company(self.request)
        if not is_platform_admin and not company:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': 'Could not determine your company — contact your Super Admin before adding employees.'})
        try:
            super().perform_create(serializer)
        except IntegrityError as exc:
            self._raise_friendly_integrity_error(exc)

    def perform_update(self, serializer):
        try:
            super().perform_update(serializer)
        except IntegrityError as exc:
            self._raise_friendly_integrity_error(exc)

    def perform_destroy(self, instance):
        self._require_privileged()
        super().perform_destroy(instance)

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        """GET /hr/employees/me/ — the caller's own Employee record, resolved directly from
        request.user.employee_profile (bypasses RBAC list scoping, same as the other
        self-service my-* actions elsewhere in this app)."""
        employee = _own_employee_or_none(request)
        if not employee:
            return Response({'detail': 'No employee profile linked to your account.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(EmployeeSerializer(employee, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='hr-contact')
    def hr_contact(self, request):
        """GET /hr/employees/hr-contact/ — best available "who to contact" email, for the
        "Contact HR" button shown when a user has no Employee profile yet (so _own_employee_or_none
        can't resolve anything, including their company — CompanyUser membership is used
        instead, which exists independently of an Employee record). Falls back through: an
        active Company Admin's email, the company's general contact email, then XERXEZ support."""
        from apps.companies.utils import resolve_company
        from apps.companies.models import CompanyUser
        company, _is_platform_admin = resolve_company(request)
        if not company:
            return Response({'email': 'info@xerxez.com', 'label': 'XERXEZ Support'})
        admin_cu = CompanyUser.objects.filter(
            company=company, role='company_admin', is_active=True, user__email__gt='',
        ).select_related('user').first()
        if admin_cu:
            return Response({'email': admin_cu.user.email, 'label': 'Company Admin'})
        if company.email:
            return Response({'email': company.email, 'label': company.name})
        return Response({'email': 'info@xerxez.com', 'label': 'XERXEZ Support'})

    @action(detail=False, methods=['get'], url_path='linkable-users')
    def linkable_users(self, request):
        if not _is_hr_privileged(request.user):
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
        User = get_user_model()
        users = User.objects.order_by('username')
        # Platform admin (super_admin) sees every user across every company; Company Admin /
        # HR Manager only see users within their own company, so they can't link an Employee
        # to someone outside their own tenant.
        from apps.companies.utils import resolve_company
        company, is_platform_admin = resolve_company(request)
        if not is_platform_admin and company:
            from apps.companies.models import CompanyUser
            user_ids = CompanyUser.objects.filter(company=company, is_active=True).values_list('user_id', flat=True)
            users = users.filter(id__in=user_ids)
        return Response(list(users.values('id', 'username', 'email', 'first_name', 'last_name')))

    @action(detail=True, methods=['get', 'post'], url_path='documents',
            parser_classes=[MultiPartParser, FormParser])
    def documents(self, request, pk=None):
        employee = self.get_object()
        if request.method == 'POST':
            if not _is_hr_privileged(request.user):
                return Response({'detail': 'Only Company Admin or HR Manager can upload documents.'}, status=status.HTTP_403_FORBIDDEN)
            ser = EmployeeDocumentSerializer(data=request.data, context={'request': request})
            ser.is_valid(raise_exception=True)
            doc = ser.save(employee=employee, company=employee.company, uploaded_by=request.user)
            _maybe_notify_document_expiring(doc)
            return Response(EmployeeDocumentSerializer(doc, context={'request': request}).data, status=status.HTTP_201_CREATED)
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

    def get_queryset(self):
        qs = super().get_queryset()
        if not _is_hr_privileged(self.request.user):
            employee = _own_employee_or_none(self.request)
            return qs.filter(employee=employee) if employee else qs.none()
        return qs

    def _require_privileged(self):
        # Regular employees manage their own attendance only through clock-in/clock-out —
        # direct create/update/delete on this base endpoint is how "Add Manual Attendance"
        # writes, and that's Admin/HR Manager only.
        if not _is_hr_privileged(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Admin only.')

    def perform_create(self, serializer):
        self._require_privileged()
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._require_privileged()
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._require_privileged()
        super().perform_destroy(instance)

    def _get_employee(self, request):
        return _own_employee_or_none(request)

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
        if not _is_hr_privileged(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        qs = self.queryset
        if emp := request.query_params.get('employee'):
            qs = qs.filter(employee=emp)
        if dept := request.query_params.get('department'):
            qs = qs.filter(employee__department_id=dept)
        if date_from := request.query_params.get('date_from'):
            qs = qs.filter(date__gte=date_from)
        if date_to := request.query_params.get('date_to'):
            qs = qs.filter(date__lte=date_to)
        if att_status := request.query_params.get('status'):
            qs = qs.filter(status=att_status)
        return Response(AttendanceSerializer(qs, many=True).data)

    @staticmethod
    def _workdays_elapsed(start, end):
        """Mon-Fri calendar days from start through end, inclusive, capped at end (never
        counts future days as 'elapsed')."""
        if end < start:
            return []
        days = []
        d = start
        while d <= end:
            if d.weekday() < 5:
                days.append(d)
            d += timedelta(days=1)
        return days

    def _week_bounds(self, today):
        return today - timedelta(days=today.weekday()), today

    @action(detail=False, methods=['get'], url_path='my-week-stats')
    def my_week_stats(self, request):
        """GET /hr/attendance/my-week-stats/ — this Mon-through-today's present/late/half_day/
        absent counts + total hours for the logged-in employee.

        Classification is driven by actual check_in/check_out/hours, not the stored `status`
        field (which can be set by "Add Manual Attendance" independently of real hours worked):
          - No check_in at all for a workday -> absent. A day the employee clocked into (even
            if not yet clocked out, e.g. today) is never counted as absent.
          - Clocked in but not yet clocked out -> not classified into any bucket yet (shift
            still in progress).
          - Clocked in and out, arrival after the late threshold -> late.
          - Clocked in and out, > 6 hours -> present.
          - Clocked in and out, 3-6 hours (inclusive) -> half_day.
          - Clocked in and out, < 3 hours -> not bucketed (too short to call present/half_day,
            but still not absent since they did show up).
        """
        employee = self._get_employee(request)
        if not employee:
            return Response({'present': 0, 'late': 0, 'half_day': 0, 'absent': 0, 'hours': 0})

        today = date.today()
        week_start, week_end = self._week_bounds(today)
        workdays = self._workdays_elapsed(week_start, week_end)
        records = {a.date: a for a in Attendance.objects.filter(employee=employee, date__range=(week_start, week_end))}

        present = late = half_day = absent = 0
        hours = 0.0
        for d in workdays:
            att = records.get(d)
            if not att or not att.check_in:
                absent += 1
                continue
            if not att.check_out:
                continue
            day_hours = float(att.hours or 0)
            hours += day_hours
            if att.status == 'late':
                late += 1
            elif day_hours > 6:
                present += 1
            elif 3 <= day_hours <= 6:
                half_day += 1
        return Response({'present': present, 'late': late, 'half_day': half_day, 'absent': absent, 'hours': round(hours, 2)})

    @action(detail=False, methods=['get'], url_path='my-month-summary')
    def my_month_summary(self, request):
        """GET /hr/attendance/my-month-summary/?year=&month= — defaults to the current month."""
        employee = self._get_employee(request)
        today = date.today()
        year = int(request.query_params.get('year') or today.year)
        month = int(request.query_params.get('month') or today.month)
        month_start = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        month_end = min(date(year, month, last_day), today) if (year, month) == (today.year, today.month) else date(year, month, last_day)
        if not employee:
            return Response({'working_days': 0, 'present': 0, 'absent': 0, 'half_day': 0, 'hours': 0, 'percentage': 0})

        workdays = self._workdays_elapsed(month_start, month_end)
        records = {a.date: a for a in Attendance.objects.filter(employee=employee, date__range=(month_start, month_end))}

        present = half_day = absent = 0
        hours = 0.0
        for d in workdays:
            att = records.get(d)
            if not att or att.status == 'absent':
                absent += 1
                continue
            hours += float(att.hours or 0)
            if att.status == 'half_day':
                half_day += 1
            else:
                present += 1
        working_days = len(workdays)
        percentage = round((present + half_day * 0.5) / working_days * 100, 1) if working_days else 0
        return Response({
            'working_days': working_days, 'present': present, 'absent': absent, 'half_day': half_day,
            'hours': round(hours, 2), 'percentage': percentage,
        })

    @action(detail=False, methods=['get'], url_path='my-calendar')
    def my_calendar(self, request):
        """GET /hr/attendance/my-calendar/?year=&month= — one entry per day of the month with a
        display status: present/late/half_day/absent (past weekday, no record), weekend, or future."""
        employee = self._get_employee(request)
        today = date.today()
        year = int(request.query_params.get('year') or today.year)
        month = int(request.query_params.get('month') or today.month)
        _, last_day = calendar.monthrange(year, month)
        records = {}
        if employee:
            records = {
                a.date: a.status for a in
                Attendance.objects.filter(employee=employee, date__year=year, date__month=month)
            }

        days = []
        for day_num in range(1, last_day + 1):
            d = date(year, month, day_num)
            if d > today:
                days.append({'date': d.isoformat(), 'status': 'future'})
            elif d.weekday() >= 5:
                days.append({'date': d.isoformat(), 'status': 'weekend'})
            elif d in records:
                days.append({'date': d.isoformat(), 'status': records[d] or 'present'})
            else:
                days.append({'date': d.isoformat(), 'status': 'absent'})
        return Response(days)

    @action(detail=False, methods=['post'], url_path='send-daily-report')
    def send_daily_report(self, request):
        """POST /hr/attendance/send-daily-report/ — admin-triggered (or hit by an external
        scheduler, e.g. a Railway Cron Job) run of the same report `send_daily_attendance_report`
        emails automatically. See that management command for the schedule-setup note."""
        if not _is_hr_privileged(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        from django.core.management import call_command
        call_command('send_daily_attendance_report')
        return Response({'message': 'Daily attendance report sent.'})

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """GET /hr/attendance/summary/?employee_id=&month=&year= — per-employee monthly counts."""
        if not _is_hr_privileged(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
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
        if not _is_hr_privileged(self.request.user):
            employee = _own_employee_or_none(self.request)
            qs = qs.filter(employee=employee) if employee else qs.none()
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(from_date__gte=date_from)
        if date_to:
            qs = qs.filter(to_date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        employee = serializer.validated_data.get('employee')
        if not _is_hr_privileged(self.request.user):
            # Regular employees can only file a leave request for themselves — ignore
            # whatever `employee` the client submitted and use their own linked profile.
            employee = _own_employee_or_none(self.request)
            if not employee:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('No employee profile linked to your account.')
        serializer.save(employee=employee, company=employee.company if employee else None)

    def perform_destroy(self, instance):
        if not _is_super_or_company_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only Super Admin or Company Admin can delete leave requests.')
        super().perform_destroy(instance)

    @action(detail=True, methods=['patch'], url_path='approve')
    def approve(self, request, pk=None):
        if not _is_hr_privileged(request.user):
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

        if not _is_hr_privileged(request.user):
            own_employee = _own_employee_or_none(request)
            if not own_employee or str(own_employee.id) != str(employee_id):
                return Response({'detail': 'You can only view your own leave balance.'}, status=status.HTTP_403_FORBIDDEN)

        year = timezone.now().year
        used = LeaveRequest.objects.filter(
            employee_id=employee_id, type=leave_type, status='approved', from_date__year=year,
        ).aggregate(total=Sum('days'))['total'] or 0
        used = float(used)

        # Unpaid leave is intentionally always uncapped — its LeavePolicy row (days_allowed=0)
        # exists only so it's visible/editable on the Leave Policy page, never to cap a balance.
        if leave_type == 'unpaid':
            return Response({'leave_type': leave_type, 'unlimited': True, 'no_policy': False, 'allowance': None, 'used': used, 'remaining': None})

        employee = Employee.objects.filter(id=employee_id).select_related('company').first()
        policy = (
            LeavePolicy.objects.filter(company=employee.company, leave_type=leave_type, is_active=True).first()
            if employee and employee.company_id else None
        )
        if not policy:
            return Response({
                'leave_type': leave_type, 'unlimited': False, 'no_policy': True,
                'allowance': None, 'used': used, 'remaining': None,
                'detail': 'Leave policy not configured — contact HR',
            })
        allowance = policy.days_allowed
        return Response({'leave_type': leave_type, 'unlimited': False, 'no_policy': False, 'allowance': allowance, 'used': used, 'remaining': max(allowance - used, 0)})


class LeavePolicyViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """Per-company leave policy configuration — days allowed per leave type, carry-forward
    rules. Company Admin/HR Manager/Super Admin can edit; everyone else can only read (their
    own company's policies), e.g. to show the correct balance on the Add Leave Request form."""
    queryset = LeavePolicy.objects.select_related('company').all()
    serializer_class = LeavePolicySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['leave_type', 'is_active']

    def _require_privileged(self):
        if not _is_hr_privileged(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Admin only.')

    def perform_create(self, serializer):
        self._require_privileged()
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._require_privileged()
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._require_privileged()
        super().perform_destroy(instance)


class ShiftViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Shift.objects.prefetch_related('employees').all()
    serializer_class = ShiftSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    module_name = 'hr'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['shift_type', 'is_active']

    def get_queryset(self):
        qs = super().get_queryset()
        if not _is_hr_privileged(self.request.user):
            employee = _own_employee_or_none(self.request)
            return qs.filter(employees=employee) if employee else qs.none()
        return qs

    def _require_privileged(self):
        if not _is_hr_privileged(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only Company Admin or HR Manager can manage shifts.')

    def perform_create(self, serializer):
        self._require_privileged()
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._require_privileged()
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._require_privileged()
        super().perform_destroy(instance)


class SalaryStructureViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = SalaryStructure.objects.select_related('employee').all()
    serializer_class = SalaryStructureSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, ReadOnlyOrHigher]
    module_name = 'hr'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee']

    def get_queryset(self):
        qs = super().get_queryset()
        if not _is_hr_privileged(self.request.user):
            employee = _own_employee_or_none(self.request)
            return qs.filter(employee=employee) if employee else qs.none()
        return qs

    def perform_create(self, serializer):
        employee = serializer.validated_data.get('employee')
        serializer.save(company=employee.company if employee else None)


class PayrollViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Payroll.objects.select_related('employee', 'generated_by').all()
    serializer_class = PayrollSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, ReadOnlyOrHigher]
    module_name = 'hr'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['employee', 'month', 'year', 'status']
    ordering_fields = ['year', 'month']

    def get_queryset(self):
        qs = super().get_queryset()
        if not _is_hr_privileged(self.request.user):
            employee = _own_employee_or_none(self.request)
            return qs.filter(employee=employee) if employee else qs.none()
        return qs

    @action(detail=False, methods=['get'], url_path='preview')
    def preview(self, request):
        """GET /hr/payroll/preview/?month=&year= — read-only dry run of what `generate` would
        produce, for the Generate Payroll tab's confirmation table. Computes the same
        basic/allowances/deductions/gross/net as `generate` (from each employee's
        SalaryStructure + Attendance), plus an informational `leave_days` count (approved
        LeaveRequest days overlapping the month) that `generate` itself doesn't use. Never
        writes to the database."""
        if not _is_hr_privileged(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        month = request.query_params.get('month')
        year = request.query_params.get('year')
        if not month or not year:
            return Response({'detail': 'month and year are required.'}, status=status.HTTP_400_BAD_REQUEST)
        month, year = int(month), int(year)
        _, working_days = calendar.monthrange(year, month)
        month_start = date(year, month, 1)
        month_end = date(year, month, working_days)

        company, is_platform_admin = self._company_context()
        employees_qs = Employee.objects.filter(status='active')
        if company:
            employees_qs = employees_qs.filter(company=company)
        elif not is_platform_admin:
            employees_qs = employees_qs.none()
        employees_qs = employees_qs.select_related('salary_structure', 'department')

        rows = []
        total_net = 0
        for emp in employees_qs:
            try:
                ss = emp.salary_structure
            except SalaryStructure.DoesNotExist:
                continue

            present_days = Attendance.objects.filter(
                employee=emp, date__range=(month_start, month_end), status__in=['present', 'late'],
            ).count()
            half_days = Attendance.objects.filter(
                employee=emp, date__range=(month_start, month_end), status='half_day',
            ).count()
            leave_days = LeaveRequest.objects.filter(
                employee=emp, status='approved', from_date__lte=month_end, to_date__gte=month_start,
            ).aggregate(total=Sum('days'))['total'] or 0

            effective_days = present_days + (half_days * 0.5)
            daily_rate = float(ss.basic_salary) / working_days if working_days else 0
            basic_earned = round(daily_rate * effective_days, 2)
            total_allowances = sum(float(v) for v in ss.allowances.values())
            total_deductions = sum(float(v) for v in ss.deductions.values())
            gross = basic_earned + total_allowances
            net = gross - total_deductions
            total_net += net

            rows.append({
                'employee_id': emp.id,
                'employee_name': emp.full_name,
                'employee_code': emp.code,
                'department_name': emp.department.name if emp.department else None,
                'basic_salary': ss.basic_salary,
                'basic_earned': basic_earned,
                'allowances': total_allowances,
                'deductions': total_deductions,
                'gross': round(gross, 2),
                'net_salary': round(net, 2),
                'working_days': working_days,
                'present_days': present_days,
                'half_days': half_days,
                'leave_days': float(leave_days),
            })

        return Response({'employees': rows, 'count': len(rows), 'total_net': round(total_net, 2)})

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        if not _is_hr_privileged(request.user):
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
        if not _is_hr_privileged(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        payroll = self.get_object()
        payroll.status = 'approved'
        payroll.save()
        return Response(PayrollSerializer(payroll).data)

    @action(detail=True, methods=['patch'], url_path='mark-paid')
    def mark_paid(self, request, pk=None):
        if not _is_hr_privileged(request.user):
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
        if not _is_hr_privileged(request.user):
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

    def get_queryset(self):
        qs = super().get_queryset()
        if not _is_hr_privileged(self.request.user):
            employee = _own_employee_or_none(self.request)
            return qs.filter(payroll__employee=employee) if employee else qs.none()
        return qs


class PerformanceReviewViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = PerformanceReview.objects.select_related('employee', 'reviewer').all()
    serializer_class = PerformanceReviewSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, ReadOnlyOrHigher]
    module_name = 'hr'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'rating']

    def get_queryset(self):
        qs = super().get_queryset()
        if not _is_hr_privileged(self.request.user):
            employee = _own_employee_or_none(self.request)
            return qs.filter(employee=employee) if employee else qs.none()
        return qs

    def _require_privileged(self):
        # A review is authored ABOUT an employee by a reviewer — an employee reviewing
        # themselves (create/edit/delete their own review) isn't a real workflow here.
        if not _is_hr_privileged(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Admin only.')

    def perform_create(self, serializer):
        self._require_privileged()
        employee = serializer.validated_data.get('employee')
        serializer.save(reviewer=self.request.user, company=employee.company if employee else None)

    def perform_update(self, serializer):
        self._require_privileged()
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._require_privileged()
        super().perform_destroy(instance)


class EmployeeDocumentViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = EmployeeDocument.objects.select_related('employee', 'uploaded_by').all()
    serializer_class = EmployeeDocumentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, ReadOnlyOrHigher]
    module_name = 'hr'
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'doc_type']

    def get_queryset(self):
        qs = super().get_queryset()
        if not _is_hr_privileged(self.request.user):
            employee = _own_employee_or_none(self.request)
            return qs.filter(employee=employee) if employee else qs.none()
        return qs

    def perform_update(self, serializer):
        if not _is_hr_privileged(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only Company Admin or HR Manager can edit documents.')
        old_expiry = serializer.instance.expiry_date
        instance = serializer.save()
        if instance.expiry_date != old_expiry:
            instance.expiry_notified = False
            instance.save(update_fields=['expiry_notified'])
        _maybe_notify_document_expiring(instance)

    def perform_destroy(self, instance):
        # Super Admin, Company Admin, and HR Manager can all delete documents — only a
        # Regular User / Read Only account is barred (matches _is_hr_privileged everywhere
        # else in this file; documents are NOT on the stricter Admin-only bar that
        # Overtime/Leave delete use, per the explicit role spec for this module).
        if not _is_hr_privileged(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only Company Admin or HR Manager can delete documents.')
        super().perform_destroy(instance)

    @action(detail=True, methods=['patch'], url_path='verify')
    def verify(self, request, pk=None):
        if not _is_hr_privileged(request.user):
            return Response({'detail': 'Only Company Admin or HR Manager can verify documents.'}, status=status.HTTP_403_FORBIDDEN)
        doc = self.get_object()
        doc.is_verified = True
        doc.verified_by = request.user
        doc.verified_at = timezone.now()
        doc.save(update_fields=['is_verified', 'verified_by', 'verified_at'])
        return Response(EmployeeDocumentSerializer(doc, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        qs = self.get_queryset()
        today = date.today()
        window_end = today + timedelta(days=30)
        return Response({
            'total': qs.count(),
            'expiring_soon': qs.filter(expiry_date__gte=today, expiry_date__lte=window_end).count(),
            'expired': qs.filter(expiry_date__lt=today).count(),
            'verified': qs.filter(is_verified=True).count(),
        })

    @action(detail=False, methods=['get'], url_path='expiring')
    def expiring(self, request):
        """GET /hr/documents/expiring/ — every document expiring within 30 days across all
        employees, for the 'Documents Expiring Soon' banner. Admin/HR Manager only — a
        regular employee's queryset above is already scoped to just their own documents."""
        if not _is_hr_privileged(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        today = date.today()
        window_end = today + timedelta(days=30)
        qs = self.get_queryset().filter(expiry_date__gte=today, expiry_date__lte=window_end).order_by('expiry_date')
        return Response(EmployeeDocumentSerializer(qs, many=True, context={'request': request}).data)


class OnboardingChecklistViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = OnboardingChecklist.objects.select_related('employee').all()
    serializer_class = OnboardingChecklistSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, ReadOnlyOrHigher]
    module_name = 'hr'
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
    permission_classes = [IsAuthenticated, ReadOnlyOrHigher]
    module_name = 'hr'
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


# ─────────────────────────────────────────────────────────────────────────────
# New: Holidays, Overtime
# ─────────────────────────────────────────────────────────────────────────────

# Curated fixed-calendar-date public holidays only (New Year's Day, national days, Christmas,
# etc.) for the "Import Public Holidays" bulk action. Deliberately excludes movable/lunar
# holidays (Eid, Diwali, Easter, ...) — this backend has no external calendar data source to
# compute those correctly for an arbitrary year, and a wrong guess is worse than an omission.
COUNTRY_PUBLIC_HOLIDAYS = {
    'india': [
        ('Republic Day', 1, 26),
        ('Labour Day', 5, 1),
        ('Independence Day', 8, 15),
        ('Gandhi Jayanti', 10, 2),
        ('Christmas', 12, 25),
    ],
    'uae': [
        ("New Year's Day", 1, 1),
        ('Commemoration Day', 12, 1),
        ('UAE National Day', 12, 2),
    ],
    'saudi_arabia': [
        ('Founding Day', 2, 22),
        ('Saudi National Day', 9, 23),
    ],
    'uk': [
        ("New Year's Day", 1, 1),
        ('Christmas Day', 12, 25),
        ('Boxing Day', 12, 26),
    ],
}


def _send_holiday_added_email(holiday, employee):
    if not employee.email:
        return
    subject = f"New Holiday Added — {holiday.name} on {holiday.date.strftime('%d %b %Y')}"
    type_label = holiday.get_holiday_type_display()

    plain = f"""
Dear {employee.full_name},

A new holiday has been added to the company calendar.

Holiday: {holiday.name}
Date: {holiday.date.strftime('%A, %d %B %Y')}
Type: {type_label}
{f"Note: {holiday.description}" if holiday.description else ""}

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
  table{{width:100%;border-collapse:collapse}}
  tr:nth-child(even) td{{background:#fafaf8}}
  td{{padding:12px 14px;font-size:14px;color:#333;vertical-align:top;border-bottom:1px solid #f0ede8}}
  td:first-child{{width:38%;font-weight:700;color:#5a5650;font-size:11px;text-transform:uppercase;letter-spacing:.09em}}
  .ftr{{background:#F8F7F4;border-top:1px solid #e8e4de;padding:18px 44px;
        text-align:center;font-size:12px;color:#9b9690}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><h1>XERXEZ</h1><p>New Holiday Added</p></div>
  <div class="body">
    <p>Dear {employee.full_name},</p>
    <p>A new holiday has been added to the company calendar.</p>
    <table>
      <tr><td>Holiday</td> <td>{holiday.name}</td></tr>
      <tr><td>Date</td>    <td>{holiday.date.strftime('%A, %d %B %Y')}</td></tr>
      <tr><td>Type</td>    <td>{type_label}</td></tr>
    </table>
  </div>
  <div class="ftr">XERXEZ HR &nbsp;·&nbsp; xerxez.com</div>
</div>
</body>
</html>"""

    send_via_resend(to=employee.email, subject=subject, html=html, text=plain, from_email=FROM_EMAIL)


class HolidayViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, ReadOnlyOrHigher]
    module_name = 'hr'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['holiday_type']
    ordering_fields = ['date']

    def perform_create(self, serializer):
        super().perform_create(serializer)
        holiday = serializer.instance
        employees = Employee.objects.filter(company=holiday.company, status='active').exclude(email='')
        for employee in employees:
            _send_holiday_added_email(holiday, employee)

    @action(detail=False, methods=['get'], url_path='upcoming')
    def upcoming(self, request):
        """GET /hr/holidays/upcoming/?limit= — next N holidays from today, for the HR
        Dashboard widget."""
        limit = int(request.query_params.get('limit', 5))
        qs = self.get_queryset().filter(date__gte=date.today()).order_by('date')[:limit]
        return Response(HolidaySerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """GET /hr/holidays/stats/ — counts for the stat cards at the top of the Holidays
        page. Recurring holidays are projected onto the current year (their stored `date`
        may be from whichever year they were first added)."""
        today = date.today()
        window_end = today + timedelta(days=30)
        total_this_year = 0
        public_this_year = 0
        upcoming_30_days = 0
        for h in self.get_queryset():
            this_year_date = h.effective_date_for_year(today.year) if h.is_recurring else (h.date if h.date.year == today.year else None)
            if this_year_date:
                total_this_year += 1
                if h.holiday_type == 'public':
                    public_this_year += 1
            next_occurrence = h.next_occurrence(today)
            if today <= next_occurrence <= window_end:
                upcoming_30_days += 1
        return Response({
            'total_this_year': total_this_year,
            'upcoming_30_days': upcoming_30_days,
            'public_this_year': public_this_year,
        })

    @action(detail=False, methods=['post'], url_path='bulk-import')
    def bulk_import(self, request):
        """POST /hr/holidays/bulk-import/ {country, year?} — adds the curated fixed-date
        public holidays for that country. Admin/HR Manager only."""
        if not _is_hr_privileged(request.user):
            return Response({'detail': 'Only Company Admin or HR Manager can import holidays.'}, status=status.HTTP_403_FORBIDDEN)
        country = request.data.get('country')
        entries = COUNTRY_PUBLIC_HOLIDAYS.get(country)
        if not entries:
            return Response({'detail': 'Unknown country.'}, status=status.HTTP_400_BAD_REQUEST)
        year = int(request.data.get('year') or date.today().year)
        company, _is_platform_admin = self._company_context()
        created = []
        for name, month, day in entries:
            obj, was_created = Holiday.objects.get_or_create(
                company=company, name=name, date=date(year, month, day),
                defaults={'holiday_type': 'public'},
            )
            if was_created:
                created.append(HolidaySerializer(obj).data)
        return Response({'created': created, 'count': len(created)})


class OvertimeViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Overtime.objects.select_related('employee', 'approved_by').all()
    serializer_class = OvertimeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, ReadOnlyOrHigher]
    module_name = 'hr'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['employee', 'status', 'rate']
    ordering_fields = ['date']

    def get_queryset(self):
        qs = super().get_queryset()
        if not _is_hr_privileged(self.request.user):
            employee = _own_employee_or_none(self.request)
            return qs.filter(employee=employee) if employee else qs.none()
        return qs

    def perform_create(self, serializer):
        employee = serializer.validated_data.get('employee')
        if not _is_hr_privileged(self.request.user):
            # Regular employees can only log overtime for themselves.
            employee = _own_employee_or_none(self.request)
            if not employee:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('No employee profile linked to your account.')
        serializer.save(employee=employee, company=employee.company if employee else None)

    def perform_destroy(self, instance):
        if not _is_super_or_company_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only Super Admin or Company Admin can delete overtime entries.')
        super().perform_destroy(instance)

    @action(detail=True, methods=['patch'], url_path='approve')
    def approve(self, request, pk=None):
        if not _is_hr_privileged(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        overtime = self.get_object()
        action_val = request.data.get('action', 'approved')
        if action_val not in ('approved', 'rejected'):
            return Response({'detail': 'action must be "approved" or "rejected".'}, status=status.HTTP_400_BAD_REQUEST)
        overtime.status = action_val
        overtime.approved_by = request.user
        overtime.approved_at = timezone.now()
        overtime.rejection_reason = request.data.get('rejection_reason', '') if action_val == 'rejected' else ''
        overtime.save()
        return Response(OvertimeSerializer(overtime).data)

    @action(detail=False, methods=['get'], url_path='by-employee')
    def by_employee(self, request):
        """GET /hr/overtime/by-employee/ — total approved overtime hours + cost per employee,
        for the Overtime page's summary."""
        totals: dict = {}
        for ot in self.get_queryset().filter(status='approved'):
            b = totals.setdefault(ot.employee_id, {
                'employee_id': ot.employee_id, 'employee_name': ot.employee.full_name,
                'total_hours': 0.0, 'total_cost': 0.0,
            })
            b['total_hours'] += float(ot.extra_hours or 0)
            b['total_cost'] += float(ot.amount or 0)
        for b in totals.values():
            b['total_hours'] = round(b['total_hours'], 2)
            b['total_cost'] = round(b['total_cost'], 2)
        return Response(list(totals.values()))
