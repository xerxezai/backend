"""Shared Resend email sending helper.

Used by any app that needs to send transactional email via Resend
(contact form, LMA notifications, etc.) instead of Django's SMTP backend.
"""
import logging

import resend
from django.conf import settings

logger = logging.getLogger(__name__)


def send_via_resend(*, to, subject, html, text, from_email, reply_to=None):
    """Send one email through Resend, falling back to Django's configured
    SMTP backend if RESEND_API_KEY isn't set — better than silently dropping
    every email an app sends through this helper (contact form, affiliate
    applications, partner approvals, …) just because Resend's domain isn't
    verified yet. Never raises — a failed email must not break the caller's
    request either way."""
    resend.api_key = settings.RESEND_API_KEY
    if not resend.api_key:
        logger.warning("RESEND_API_KEY is not set — falling back to SMTP (subject=%r, to=%r)", subject, to)
        _send_via_smtp_fallback(to=to, subject=subject, html=html, text=text, reply_to=reply_to)
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


def _send_via_smtp_fallback(*, to, subject, html, text, reply_to=None):
    """SMTP fallback for send_via_resend. Always sends from
    settings.DEFAULT_FROM_EMAIL (the authenticated EMAIL_HOST_USER address),
    not whatever `from_email` the Resend call was given — Resend callers
    pass Resend's shared onboarding@resend.dev sender (since xerxez.com
    isn't verified there yet), but Gmail SMTP requires the From address to
    match the authenticated account, so reusing that value here would just
    trade one silent failure for another."""
    if not settings.EMAIL_HOST_USER:
        logger.warning("EMAIL_HOST_USER is not set either — email skipped entirely (subject=%r, to=%r)", subject, to)
        return
    try:
        from django.core.mail import EmailMultiAlternatives
        recipients = [to] if isinstance(to, str) else to
        msg = EmailMultiAlternatives(
            subject, text, settings.DEFAULT_FROM_EMAIL, recipients,
            reply_to=[reply_to] if reply_to else None,
        )
        if html:
            msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)
    except Exception as exc:
        logger.error("SMTP fallback email failed (subject=%r, to=%r): %s", subject, to, exc)


# ── Shared v2-themed HTML email shell ────────────────────────────────────────
# Used by every email in the LMA/Academy surface — contact form, affiliate
# applications, instructor applications, partner course listing (routed
# through the contact form), and their approve/reject follow-ups — so they
# all look like one system instead of each hand-rolling its own palette.
# Deliberately NOT used by the ERP welcome email above or apps.partners
# (the unrelated ERP reseller program), which keep their own amber theme.
V2_NAVY = '#071a33'
V2_RED = '#D93522'
V2_BG = '#F4F7FA'


def render_v2_email(*, title, body_html, cta_label=None, cta_url=None):
    """Wraps `body_html` in the shared v2 email shell: #F4F7FA background,
    white card (border-radius 8px, max-width 600px), navy header with the
    XERXEZ wordmark, navy heading / gray body text, red accents, and a navy
    footer with the copyright line. `body_html` should be plain paragraph/
    table markup — no need to repeat colors, this shell sets sane defaults."""
    cta_block = ''
    if cta_label and cta_url:
        cta_block = f'''
        <div style="text-align:center;margin:30px 0 6px">
          <a href="{cta_url}" style="display:inline-block;background:{V2_RED};color:#ffffff;text-decoration:none;
             font-family:'Segoe UI',Arial,sans-serif;font-size:14px;font-weight:700;padding:13px 30px;border-radius:8px">
            {cta_label}
          </a>
        </div>'''
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{title}</title></head>
<body style="margin:0;padding:32px 16px;background:{V2_BG};font-family:'Segoe UI',Arial,sans-serif;">
  <div style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 4px 24px rgba(7,26,51,0.08)">
    <div style="background:{V2_NAVY};padding:28px 36px;text-align:center">
      <div style="color:#ffffff;font-size:22px;font-weight:800;letter-spacing:0.04em;font-family:'Segoe UI',Arial,sans-serif">XERXEZ</div>
    </div>
    <div style="padding:36px 36px 8px;color:#4b5563;font-size:14px;line-height:1.7;font-family:'Segoe UI',Arial,sans-serif">
      <h2 style="color:{V2_NAVY};font-size:19px;font-weight:800;margin:0 0 16px;font-family:'Segoe UI',Arial,sans-serif">{title}</h2>
      {body_html}
      {cta_block}
    </div>
    <div style="height:28px"></div>
    <div style="background:{V2_NAVY};padding:18px 36px;text-align:center">
      <div style="color:rgba(255,255,255,0.55);font-size:12px;font-family:'Segoe UI',Arial,sans-serif">© 2026 XERXEZ. All rights reserved.</div>
    </div>
  </div>
</body></html>'''


def v2_detail_table(rows):
    """rows: list of (label, value) pairs -> an HTML table matching the v2
    shell's palette (red-accented label column, light zebra striping)."""
    trs = ''.join(
        f'''<tr style="{"background:#fafbfc;" if i % 2 else ""}">
              <td style="padding:10px 14px;font-size:11px;font-weight:700;color:{V2_RED};text-transform:uppercase;
                  letter-spacing:0.06em;border-bottom:1px solid #eef1f5;vertical-align:top;width:34%">{label}</td>
              <td style="padding:10px 14px;font-size:14px;color:#1f2937;border-bottom:1px solid #eef1f5;vertical-align:top">{value}</td>
            </tr>'''
        for i, (label, value) in enumerate(rows)
    )
    return f'<table style="width:100%;border-collapse:collapse;margin:18px 0">{trs}</table>'


def v2_message_box(text):
    """A left-red-bordered box for a free-text message/note, matching the
    v2 shell."""
    return (
        f'<div style="background:{V2_BG};border-left:3px solid {V2_RED};border-radius:0 8px 8px 0;'
        f'padding:16px 20px;margin:18px 0;font-size:14px;line-height:1.7;color:#374151;'
        f'white-space:pre-wrap;word-break:break-word">{text}</div>'
    )


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
