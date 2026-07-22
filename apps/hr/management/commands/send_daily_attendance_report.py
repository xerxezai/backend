"""Emails a daily attendance summary to xerxez.in@gmail.com.

Nothing in this Django deployment schedules jobs on its own — there's no Celery/beat,
APScheduler, or django-crontab installed, and the Procfile runs a single `web` gunicorn
process only. To actually fire this at 6 PM every day, point an external scheduler at it:

  * Railway Cron Job (recommended) — add a new service in the Railway project, type
    "Cron Job", schedule `0 18 * * *`, start command:
        python manage.py send_daily_attendance_report
  * Or hit the equivalent authenticated endpoint on a schedule instead (e.g. from
    GitHub Actions or cron-job.org): POST /api/v1/hr/attendance/send-daily-report/
    with a staff user's Bearer token — see AttendanceViewSet.send_daily_report.
"""
from datetime import date

from django.core.management.base import BaseCommand

from apps.core.email import send_via_resend
from apps.hr.models import Attendance, Employee

REPORT_EMAIL = 'xerxez.in@gmail.com'
# TEMPORARY: xerxez.com is not yet verified in Resend — see apps.contact.views for the
# same note; switch to a verified xerxez.com sender once domain verification completes.
FROM_EMAIL = 'onboarding@resend.dev'


class Command(BaseCommand):
    help = "Emails today's attendance summary (present/absent/late/half-day + absentee list) to xerxez.in@gmail.com."

    def handle(self, *args, **options):
        today = date.today()
        active_employees = Employee.objects.filter(status='active').select_related('department')
        today_records = {a.employee_id: a for a in Attendance.objects.filter(date=today).select_related('employee')}

        total = active_employees.count()
        present = late = half_day = 0
        absent_employees = []

        for emp in active_employees:
            att = today_records.get(emp.id)
            if not att or att.status == 'absent':
                absent_employees.append(emp)
            elif att.status == 'late':
                late += 1
            elif att.status == 'half_day':
                half_day += 1
            else:
                present += 1

        absent_count = len(absent_employees)
        date_label = today.strftime('%d %B %Y')

        plain = f"""
Daily Attendance Report — {date_label}
{'=' * (26 + len(date_label))}
Total Employees : {total}
Present Today    : {present}
Absent Today     : {absent_count}
Late Today       : {late}
Half Days Today  : {half_day}

Absent Employees
-----------------
{chr(10).join(f'- {e.full_name} ({e.code})' for e in absent_employees) if absent_employees else 'None — full attendance today.'}
""".strip()

        rows = ''.join(f'<tr><td style="padding:6px 10px">{e.full_name}</td><td style="padding:6px 10px;color:#6B6B6B">{e.department.name if e.department else "—"}</td></tr>' for e in absent_employees)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
  .wrap{{max-width:560px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
  .hdr{{background:linear-gradient(135deg,#1a1208 0%,#0f0a05 100%);padding:32px 40px;text-align:center}}
  .hdr h1{{color:#C9883A;font-family:Georgia,serif;font-size:22px;margin:0 0 4px}}
  .hdr p{{color:rgba(255,255,255,.45);font-size:12.5px;margin:0}}
  .stats{{display:table;width:100%;padding:24px 40px 8px;box-sizing:border-box}}
  .stat{{display:table-cell;text-align:center;padding:0 4px}}
  .stat b{{display:block;font-size:22px;color:#1a1208}}
  .stat span{{display:block;font-size:10.5px;color:#9b9690;text-transform:uppercase;letter-spacing:.06em;margin-top:2px}}
  .section{{padding:8px 40px 32px}}
  .section h3{{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#5a5650;margin:20px 0 8px}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  tr:nth-child(even) td{{background:#fafaf8}}
  .ftr{{background:#F8F7F4;border-top:1px solid #e8e4de;padding:16px 40px;text-align:center;font-size:11.5px;color:#9b9690}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><h1>XERXEZ</h1><p>Daily Attendance Report — {date_label}</p></div>
  <div class="stats">
    <div class="stat"><b>{total}</b><span>Employees</span></div>
    <div class="stat"><b style="color:#10b981">{present}</b><span>Present</span></div>
    <div class="stat"><b style="color:#ef4444">{absent_count}</b><span>Absent</span></div>
    <div class="stat"><b style="color:#f59e0b">{late}</b><span>Late</span></div>
    <div class="stat"><b style="color:#6366f1">{half_day}</b><span>Half Day</span></div>
  </div>
  <div class="section">
    <h3>Absent Employees</h3>
    {'<table>' + rows + '</table>' if absent_employees else '<p style="color:#6B6B6B;font-size:13px">Full attendance today — no absences.</p>'}
  </div>
  <div class="ftr">XERXEZ HR &nbsp;·&nbsp; xerxez.com</div>
</div>
</body>
</html>"""

        send_via_resend(
            to=REPORT_EMAIL,
            subject=f'Daily Attendance Report — {date_label}',
            html=html, text=plain, from_email=FROM_EMAIL,
        )
        self.stdout.write(self.style.SUCCESS(f'Daily attendance report sent for {date_label}.'))
