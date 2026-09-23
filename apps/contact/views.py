import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.email import send_via_resend, render_v2_email, v2_detail_table, v2_message_box
from apps.crm.models import Lead
from apps.rbac.views import IsSuperAdmin
from .models import ContactMessage
from .serializers import ContactMessageSerializer, ContactInquirySerializer

logger = logging.getLogger(__name__)

ADMIN_EMAIL = getattr(settings, 'CONTACT_ADMIN_EMAIL', 'info@xerxez.com')
# TEMPORARY: xerxez.com is not yet verified in Resend, so sends must use
# Resend's shared onboarding@resend.dev sender until domain verification
# completes. Switch back to CONTACT_FROM_EMAIL (info@xerxez.com) once verified.
FROM_EMAIL = 'onboarding@resend.dev'


def _send_via_resend(*, to, subject, html, text, reply_to=None):
    send_via_resend(to=to, subject=subject, html=html, text=text, from_email=FROM_EMAIL, reply_to=reply_to)


URGENCY_LABELS = {
    'normal':   'Normal (within 24 h)',
    'urgent':   'Urgent (within 4 h)',
    'critical': 'Critical — Immediate',
}

# (label, model field name) — only fields with a value are shown, so each
# service's enquiry email only lists the qualification fields relevant to it.
QUALIFICATION_FIELDS = [
    ('Country', 'country'),
    ('Industry', 'industry'),
    ('Current Challenge', 'current_challenge'),
    ('Plan Interest', 'plan_interest'),
    ('Team Size', 'team_size'),
    ('Timeline', 'timeline'),
    ('ERP Modules of Interest', 'erp_modules'),
    ('Budget', 'budget_range'),
    ('Current Tech Stack', 'tech_stack'),
    ('Deployment Environment', 'deployment_env'),
    ('Number of Developers', 'num_developers'),
    ('Cloud Provider Preference', 'cloud_provider'),
    ('Current Infrastructure', 'current_infra'),
    ('Migration Needed', 'migration_needed'),
    ('Project Type', 'project_type'),
    ('Project Timeline', 'project_timeline'),
    ('Approximate Budget', 'approx_budget'),
    ('Team Size for Training', 'training_team_size'),
    ('Training Mode', 'training_mode'),
    ('Training Duration', 'training_duration'),
    ('Topics of Interest', 'topics_of_interest'),
    ('Course Name(s)', 'course_names'),
    ('Platform URL', 'platform_url'),
    ('Course URL(s)', 'course_url'),
    ('Coupon Code', 'coupon_code'),
    ('Discount Amount', 'discount_amount'),
    ('Heard Via', 'hear_about_us'),
]


def _qualification_rows(m: ContactMessage):
    return [(label, getattr(m, field)) for label, field in QUALIFICATION_FIELDS if getattr(m, field)]


def _notification_email(m: ContactMessage) -> tuple:
    """Build plain-text + HTML notification email for XERXEZ team (v2 theme)."""
    qual_rows = _qualification_rows(m)
    submitted_at = timezone.localtime(m.created_at).strftime('%d %b %Y, %I:%M %p')
    qual_plain = "\n".join(f"{label:<26}: {value}" for label, value in qual_rows)

    plain = f"""
New Contact Form Submission — XERXEZ Website
=============================================
Name          : {m.full_name}
Email         : {m.email}
Phone         : {m.phone or '—'}
Company       : {m.company or '—'}
Service       : {m.service or '—'}
Submitted at  : {submitted_at}

{qual_plain}

Message
-------
{m.message}

=============================================
Reply directly to {m.email} to respond.
""".strip()

    rows = [
        ('Name', m.full_name),
        ('Email', f'<a href="mailto:{m.email}" style="color:#D93522">{m.email}</a>'),
        ('Phone', m.phone or '—'),
        ('Company', m.company or '—'),
        ('Service', m.service or '—'),
        *qual_rows,
        ('Submitted at', submitted_at),
    ]
    body_html = (
        v2_detail_table(rows)
        + v2_message_box(m.message)
    )
    html = render_v2_email(
        title='New Contact Form Submission',
        body_html=body_html,
        cta_label=f"Reply to {m.full_name.split()[0]}",
        cta_url=f"mailto:{m.email}?subject=Re%3A {m.subject or 'Your Enquiry'}",
    )
    return plain, html


def _auto_reply_email(m: ContactMessage) -> tuple:
    """Build auto-reply email for the person who submitted the form (v2 theme)."""
    first = m.full_name.split()[0] if m.full_name else 'there'

    plain = f"""Hi {first},

We received your enquiry and will respond within 24 hours.

Best regards,
The XERXEZ Team
info@xerxez.com | xerxez.com
""".strip()

    body_html = f'<p>Hi {first}, we received your enquiry and will respond within <strong>24 hours</strong>.</p>'
    html = render_v2_email(title='Thank you for contacting XERXEZ', body_html=body_html)
    return plain, html


class ContactMessageCreateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """Pre-warm endpoint — keeps Railway awake and confirms API is ready."""
        return Response({"status": "ready", "endpoint": "contact"}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ContactMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            instance: ContactMessage = serializer.save()
        except Exception as exc:
            logger.error("Contact save failed: %s", exc, exc_info=True)
            return Response(
                {'success': False, 'message': 'Failed to save your message. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        is_partner_course_listing = instance.service == 'Partner Course Listing'

        # 1. Notify XERXEZ team — same notification email (already lists every
        # form field: name, email, phone, company, service, qualification
        # rows, message, submitted-at) for every service, just a distinct
        # subject line for partner course listing requests so they're easy
        # to spot/filter.
        if is_partner_course_listing:
            subject = f"New Partner Course Listing Request — {instance.company or instance.full_name}"
        else:
            subject = f"New Contact Form Submission — {instance.subject or instance.service or 'General Enquiry'} from {instance.full_name}"

        plain, html = _notification_email(instance)
        _send_via_resend(
            to=ADMIN_EMAIL,
            subject=subject,
            html=html,
            text=plain,
            reply_to=instance.email,
        )

        # 2. Auto-reply to enquirer — partner course listing gets its own
        # subject/body (48h review turnaround) instead of the generic 24h copy.
        if is_partner_course_listing:
            first = instance.full_name.split()[0] if instance.full_name else 'there'
            _send_via_resend(
                to=instance.email,
                subject="Thank you for your interest in listing courses on XERXEZ",
                text=(
                    f"Hi {first},\n\n"
                    f"Thank you for your interest in listing your courses on XERXEZ.\n"
                    f"We'll review and contact you within 48 hours.\n\n"
                    f"Best regards,\nThe XERXEZ Team\ninfo@xerxez.com | xerxez.com"
                ),
                html=render_v2_email(
                    title="Thank you for your interest in listing courses on XERXEZ",
                    body_html=(
                        f'<p>Hi {first}, thank you for your interest in listing your courses on XERXEZ. '
                        f"We'll review and contact you within <strong>48 hours</strong>.</p>"
                    ),
                ),
            )
        else:
            ar_plain, ar_html = _auto_reply_email(instance)
            _send_via_resend(
                to=instance.email,
                subject="Thank you for contacting XERXEZ",
                html=ar_html,
                text=ar_plain,
            )

        # 3. Auto-create a CRM lead so sales can follow up — best-effort, a CRM hiccup
        # must never block the visitor's enquiry from being saved and acknowledged.
        try:
            Lead.objects.create(
                name=instance.full_name,
                company=instance.company or '',
                email=instance.email,
                phone=instance.phone or '',
                source='website',
                status='new',
                notes=f"{instance.subject or 'Website enquiry'}\n\n{instance.message}",
            )
        except Exception as exc:
            logger.error("CRM lead creation failed: %s", exc, exc_info=True)

        return Response(
            {
                'success': True,
                'message': 'Your enquiry has been received. We will get back to you within 24 hours.',
            },
            status=status.HTTP_201_CREATED,
        )


# ── Contact Inquiries admin (super_admin only) ───────────────────────────────

class ContactInquiryListView(APIView):
    """GET /api/v1/contact/inquiries/ — all contact messages, with filters."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = ContactMessage.objects.select_related('assigned_to').all()
        p = request.query_params

        if p.get('status'):
            qs = qs.filter(status=p['status'])
        if p.get('priority'):
            qs = qs.filter(priority=p['priority'])
        if p.get('service'):
            qs = qs.filter(service=p['service'])
        if p.get('date_from'):
            qs = qs.filter(created_at__date__gte=p['date_from'])
        if p.get('date_to'):
            qs = qs.filter(created_at__date__lte=p['date_to'])
        if p.get('search'):
            s = p['search']
            qs = qs.filter(Q(full_name__icontains=s) | Q(email__icontains=s) | Q(company__icontains=s))

        return Response(ContactInquirySerializer(qs, many=True).data)


class ContactInquiryDetailView(APIView):
    """GET/PUT/DELETE /api/v1/contact/inquiries/{id}/"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def get(self, request, pk):
        try:
            inquiry = ContactMessage.objects.select_related('assigned_to').get(pk=pk)
        except ContactMessage.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        return Response(ContactInquirySerializer(inquiry).data)

    def put(self, request, pk):
        try:
            inquiry = ContactMessage.objects.get(pk=pk)
        except ContactMessage.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        data = request.data
        if 'status' in data:
            if data['status'] not in dict(ContactMessage.STATUS_CHOICES):
                return Response({'error': f'status must be one of: {", ".join(dict(ContactMessage.STATUS_CHOICES))}'}, status=400)
            inquiry.status = data['status']
            if data['status'] == 'replied' and not inquiry.replied_at:
                inquiry.replied_at = timezone.now()
        if 'priority' in data:
            if data['priority'] not in dict(ContactMessage.PRIORITY_CHOICES):
                return Response({'error': f'priority must be one of: {", ".join(dict(ContactMessage.PRIORITY_CHOICES))}'}, status=400)
            inquiry.priority = data['priority']
        if 'assigned_to' in data:
            inquiry.assigned_to_id = data['assigned_to'] or None
        if 'notes' in data:
            inquiry.notes = data['notes'] or ''
        inquiry.save()
        return Response(ContactInquirySerializer(inquiry).data)

    def delete(self, request, pk):
        try:
            inquiry = ContactMessage.objects.get(pk=pk)
        except ContactMessage.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        inquiry.delete()
        return Response(status=204)


class ContactInquiryStatsView(APIView):
    """GET /api/v1/contact/inquiries/stats/"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = ContactMessage.objects.all()
        now = timezone.now()
        return Response({
            'total': qs.count(),
            'new': qs.filter(status='new').count(),
            'reviewed': qs.filter(status='reviewed').count(),
            'replied': qs.filter(status='replied').count(),
            'closed': qs.filter(status='closed').count(),
            'high_priority': qs.filter(priority='high').count(),
            'this_week': qs.filter(created_at__gte=now - timedelta(days=7)).count(),
            'this_month': qs.filter(created_at__gte=now - timedelta(days=30)).count(),
        })
