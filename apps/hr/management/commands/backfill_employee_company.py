"""One-time-safe data fix: set company on any Employee row that has none.

Employee.company = NULL rows are invisible to every company-scoped query (Company
Admin's employee list, and by extension attendance/leave/payroll/performance/overtime
for that employee too) — even though the record itself, and any user link on it, is
otherwise completely valid. This has been silently produced by two other paths in
this app: setup_admin_employees (runs on every deploy) and `link_employee_user
--create`, both fixed to set company going forward — this command repairs any row
those already created before the fix.

Idempotent (only ever touches company IS NULL rows) and reports rows it can't safely
resolve rather than guessing, so it's safe to leave in the deploy chain.
"""
from django.core.management.base import BaseCommand

from apps.hr.models import Employee


class Command(BaseCommand):
    help = "Backfill company on any Employee row where it's missing."

    def handle(self, *args, **kwargs):
        from apps.companies.utils import get_user_company_or_default

        orphaned = Employee.objects.filter(company__isnull=True)
        total = orphaned.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No orphaned Employee rows — nothing to do."))
            return

        fixed = skipped = 0
        for employee in orphaned:
            company = get_user_company_or_default(employee.user) if employee.user_id else None
            if company:
                employee.company = company
                employee.save(update_fields=['company'])
                self.stdout.write(f"Employee #{employee.id} ({employee.full_name}) -> company_id={company.id}")
                fixed += 1
            else:
                self.stdout.write(self.style.WARNING(
                    f"Employee #{employee.id} ({employee.full_name}, user_id={employee.user_id}) — "
                    f"could not determine a company (no linked user, or user has no CompanyUser "
                    f"membership and more than one Company exists). Left as-is; set manually."
                ))
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Done — fixed {fixed}, skipped {skipped} of {total}."))
