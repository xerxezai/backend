"""One-time-safe data fix: seed default leave policies onto any company that predates the
Leave Policy feature. New companies get these automatically (see CompanyListView.post ->
create_default_leave_policies) — this repairs existing ones.

Idempotent (create_default_leave_policies uses get_or_create per leave_type), so it is safe
to leave in the deploy chain."""
from django.core.management.base import BaseCommand

from apps.companies.models import Company
from apps.hr.models import create_default_leave_policies


class Command(BaseCommand):
    help = "Seed default leave policies for every company that doesn't have any yet."

    def handle(self, *args, **kwargs):
        for company in Company.objects.all():
            before = company.leave_policies.count()
            create_default_leave_policies(company)
            after = company.leave_policies.count()
            self.stdout.write(f"{company.name}: {after - before} policy(ies) created, {after} total.")
        self.stdout.write(self.style.SUCCESS("Done!"))
