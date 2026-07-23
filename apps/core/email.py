"""Shared Resend email sending helper.

Used by any app that needs to send transactional email via Resend
(contact form, LMA notifications, etc.) instead of Django's SMTP backend.
"""
import logging

import resend
from django.conf import settings

logger = logging.getLogger(__name__)


def send_via_resend(*, to, subject, html, text, from_email, reply_to=None):
    """Send one email through Resend. Never raises — a failed email must not break the caller's request."""
    resend.api_key = settings.RESEND_API_KEY
    if not resend.api_key:
        logger.error("RESEND_API_KEY is not set — skipping email send (subject=%r, to=%r)", subject, to)
        return
    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "html": html,
        "text": text,
    }
    if reply_to:
        params["reply_to"] = reply_to
    try:
        resend.Emails.send(params)
    except Exception as exc:
        logger.error("Resend email failed (subject=%r, to=%r): %s", subject, to, exc)


WELCOME_FROM_EMAIL = 'onboarding@resend.dev'

# (plain-text block, html <li>/<ol> block) per role — shown under the login details in the
# new-user welcome email. Falls back to _DEFAULT_ROLE_CONTENT for any role not listed here
# (e.g. read_only).
_ROLE_CONTENT = {
    'regular_user': (
        """YOUR MAIN TASKS:
- Clock In when you arrive at the office
- Clock Out when you leave
- Apply for leave when needed
- View your payslips
- Update your profile

HOW TO MARK ATTENDANCE:
1. Go to xerxez.com/erp on your office computer
2. Log in with your credentials below
3. Click "My Attendance" in the sidebar
4. Click "Clock In" when you arrive
5. Click "Clock Out" when you leave""",
        """<div class="section"><strong>Your Main Tasks</strong>
<ul><li>Clock In when you arrive at the office</li><li>Clock Out when you leave</li>
<li>Apply for leave when needed</li><li>View your payslips</li><li>Update your profile</li></ul>
<strong>How to Mark Attendance</strong>
<ol><li>Go to xerxez.com/erp on your office computer</li><li>Log in with your credentials below</li>
<li>Click &ldquo;My Attendance&rdquo; in the sidebar</li><li>Click &ldquo;Clock In&rdquo; when you arrive</li>
<li>Click &ldquo;Clock Out&rdquo; when you leave</li></ol></div>""",
    ),
    'company_admin': (
        """AS COMPANY ADMIN YOU CAN:
- Manage your company's users
- View all attendance records
- Manage payroll
- Access all HR modules
- Add, edit and delete company data""",
        """<div class="section"><strong>As Company Admin You Can</strong>
<ul><li>Manage your company's users</li><li>View all attendance records</li><li>Manage payroll</li>
<li>Access all HR modules</li><li>Add, edit and delete company data</li></ul></div>""",
    ),
    'module_admin': (
        """AS MODULE ADMIN YOU CAN:
- Access your assigned modules
- View all company data in your modules
- Add, edit and delete records""",
        """<div class="section"><strong>As Module Admin You Can</strong>
<ul><li>Access your assigned modules</li><li>View all company data in your modules</li>
<li>Add, edit and delete records</li></ul></div>""",
    ),
}
_DEFAULT_ROLE_CONTENT = (
    """YOU CAN:
- Access your assigned modules
- View and manage your own data""",
    """<div class="section"><strong>You Can</strong>
<ul><li>Access your assigned modules</li><li>View and manage your own data</li></ul></div>""",
)


def send_welcome_email(full_name, email, username, password, company_name=None, role=None):
    """Send the new-user welcome email (login details + role-specific getting-started
    instructions) via Resend. Used by both User Management (Super Admin) and My Company
    Users (Company Admin) right after a new ERP user account is created. Never raises."""
    if not email:
        return False

    role_plain, role_html = _ROLE_CONTENT.get(role, _DEFAULT_ROLE_CONTENT)
    company_line_plain = f"\nYour Company: {company_name}" if company_name else ""
    company_line_html = f'<p><strong>Company:</strong> {company_name}</p>' if company_name else ''

    subject = f"Welcome to XERXEZ ERP{' — ' + company_name if company_name else ''}"

    plain = f"""Hi {full_name},

Welcome to XERXEZ ERP! Your account has been created successfully.
{company_line_plain}

YOUR LOGIN DETAILS
———————————————————
Login URL: xerxez.com/erp
Username: {username}
Password: {password}

Please change your password after your first login.

{role_plain}

NEED HELP?
———————————————————
Email: info@xerxez.com
Phone: +971 56 786 7451
Website: xerxez.com

Welcome aboard!
XERXEZ Team""".strip()

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
.wrap{{max-width:580px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
.hdr{{background:linear-gradient(135deg,#1a1208 0%,#0f0a05 100%);padding:36px 40px;text-align:center}}
.hdr h1{{color:#C9883A;font-family:Georgia,serif;font-size:22px;margin:0 0 4px;letter-spacing:.04em}}
.hdr p{{color:rgba(255,255,255,.55);font-size:13px;margin:0}}
.body{{padding:36px 40px;font-size:14px;color:#333;line-height:1.74}}
.creds{{background:#fafaf8;border-radius:10px;border:1px solid #f0ede8;border-left:3px solid #C9883A;padding:16px 20px;margin:20px 0;font-size:13px}}
.creds p{{margin:4px 0;color:#5a5650}}
.creds strong{{color:#1a1a1a}}
.section{{background:#fafaf8;border-radius:10px;padding:16px 20px;margin:16px 0;font-size:13px;color:#5a5650}}
.section strong{{color:#1a1a1a;display:block;margin-bottom:6px}}
.section ul,.section ol{{margin:6px 0 14px;padding-left:20px}}
.section ul:last-child,.section ol:last-child{{margin-bottom:0}}
.cta{{display:inline-block;margin-top:10px;padding:13px 32px;background:linear-gradient(145deg,#e8a84e,#C9883A);color:#fff!important;font-size:13px;font-weight:700;border-radius:100px;text-decoration:none;box-shadow:0 4px 12px rgba(201,136,58,.28)}}
.ftr{{background:#1a1a1a;border-top:1px solid #2c2c2c;padding:18px 40px;text-align:center;font-size:12px;color:rgba(255,255,255,.45)}}
</style></head><body><div class="wrap">
<div class="hdr"><h1>XERXEZ</h1><p>Enterprise ERP</p></div>
<div class="body">
<p>Hi {full_name},</p>
<p>Welcome to XERXEZ ERP! Your account has been created successfully.</p>
{company_line_html}
<div class="creds">
<p><strong>Login URL:</strong> xerxez.com/erp</p>
<p><strong>Username:</strong> {username}</p>
<p><strong>Password:</strong> {password}</p>
</div>
<p style="color:#9b9690">Please change your password after your first login.</p>
{role_html}
<div style="text-align:center"><a class="cta" href="https://www.xerxez.com/erp">Log In to XERXEZ ERP</a></div>
<p style="margin-top:24px">Need help? Email <a href="mailto:info@xerxez.com" style="color:#C9883A">info@xerxez.com</a>
or call +971 56 786 7451.</p>
<p>Welcome aboard!<br><strong>The XERXEZ Team</strong></p>
</div>
<div class="ftr">XERXEZ &nbsp;·&nbsp; info@xerxez.com &nbsp;·&nbsp; xerxez.com</div>
</div></body></html>"""

    try:
        send_via_resend(to=email, subject=subject, html=html, text=plain, from_email=WELCOME_FROM_EMAIL)
        return True
    except Exception:
        logger.exception("send_welcome_email failed (to=%r)", email)
        return False
