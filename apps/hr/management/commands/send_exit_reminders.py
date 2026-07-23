"""Emails each company's HR (Company Admin / HR Manager) 3 days before an employee's last
working day, for every exit that hasn't been completed yet.

Nothing in this Django deployment schedules jobs on its own — there's no Celery/beat,
APScheduler, or django-crontab installed, and the Procfile runs a single `web` gunicorn
process only. To actually fire this daily, point an external scheduler at it (same approach
as send_daily_attendance_report / check_expiring_documents / send_onboarding_reminders):

  * Railway Cron Job (recommended) — add a new service in the Railway project, type
    "Cron Job", schedule e.g. `0 8 * * *`, start command:
        python manage.py send_exit_reminders

`notice_reminder_sent` prevents re-emailing the same exit on every subsequent run.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.core.email import send_via_resend
from apps.hr.models import ExitManagement
from apps.hr.views import _hr_recipient_emails

FROM_EMAIL = 'onboarding@resend.dev'


class Command(BaseCommand):
    help = "Emails HR 3 days before an employee's last working day."

    def handle(self, *args, **options):
        target_day = date.today() + timedelta(days=3)
        qs = ExitManagement.objects.filter(
            last_working_day=target_day, notice_reminder_sent=False, completed_at__isnull=True,
        ).select_related('employee', 'company')

        sent = 0
        for exit_record in qs:
            employee = exit_record.employee
            recipients = _hr_recipient_emails(exit_record.company)
            subject = f"Last Working Day in 3 Days — {employee.full_name}"
            plain = f"""
{employee.full_name}'s last working day is {exit_record.last_working_day.strftime('%d %b %Y')} — 3 days from now.

Make sure offboarding (checklist, settlement, exit interview) is on track.

— XERXEZ HR
""".strip()
            html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
  .wrap{{max-width:560px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
  .hdr{{background:linear-gradient(135deg,#1a1208 0%,#0f0a05 100%);padding:36px 44px;text-align:center}}
  .hdr h1{{color:#C9883A;font-family:Georgia,serif;font-size:24px;margin:0 0 6px}}
  .hdr p{{color:rgba(255,255,255,.42);font-size:13px;margin:0}}
  .body{{padding:36px 44px;font-size:14px;color:#333}}
  .ftr{{background:#F8F7F4;border-top:1px solid #e8e4de;padding:18px 44px;text-align:center;font-size:12px;color:#9b9690}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><h1>XERXEZ</h1><p>Notice Period Reminder</p></div>
  <div class="body">
    <p><strong>{employee.full_name}</strong>'s last working day is <strong>{exit_record.last_working_day.strftime('%d %b %Y')}</strong> — 3 days from now.</p>
    <p>Make sure offboarding (checklist, settlement, exit interview) is on track.</p>
  </div>
  <div class="ftr">XERXEZ HR &nbsp;·&nbsp; xerxez.com</div>
</div>
</body>
</html>"""
            send_via_resend(to=recipients, subject=subject, html=html, text=plain, from_email=FROM_EMAIL)
            exit_record.notice_reminder_sent = True
            exit_record.save(update_fields=['notice_reminder_sent'])
            sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} exit reminder(s) for last working day {target_day.isoformat()}.'))
