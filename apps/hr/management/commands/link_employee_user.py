"""Link a User account to an Employee record (sets Employee.user_id).

Usage:
    python manage.py link_employee_user <username-or-email>
    python manage.py link_employee_user <username-or-email> --employee <code-or-id-or-name>
    python manage.py link_employee_user <username-or-email> --create
    python manage.py link_employee_user <username-or-email> --force

Resolution order for the employee to link, when --employee is not given:
  1. Employee.email matches the user's email (case-insensitive)
  2. Employee.full_name matches the user's username (case-insensitive)
  3. Employee.full_name matches the user's first_name (case-insensitive)

If none match and --create is passed, a new Employee record is created for
the user. Otherwise the command reports what it found and exits without
changing anything, so it is safe to run repeatedly to check state.

If the matched Employee is already linked to a *different* user, the command
refuses to overwrite unless --force is passed.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.hr.models import Employee


class Command(BaseCommand):
    help = "Link a User account (by username or email) to an Employee record."

    def add_arguments(self, parser):
        parser.add_argument('user', help='Username or email of the account to link')
        parser.add_argument('--employee', help='Employee code, id, or full name to link to (auto-detected if omitted)')
        parser.add_argument('--create', action='store_true', help='Create a new Employee record if no match is found')
        parser.add_argument('--force', action='store_true', help='Overwrite an existing link on the matched employee')

    def handle(self, *args, **opts):
        User = get_user_model()
        ident = opts['user']

        try:
            user = User.objects.get(models_q_username_or_email(ident))
        except User.DoesNotExist:
            raise CommandError(f"No user found matching '{ident}' (checked username and email).")
        except User.MultipleObjectsReturned:
            raise CommandError(f"Multiple users match '{ident}' — pass a more specific username or email.")

        employee = self._resolve_employee(user, opts.get('employee'))

        if employee is None:
            if opts['create']:
                from apps.companies.utils import get_user_company_or_default
                employee = Employee.objects.create(
                    code=self._gen_code(),
                    full_name=user.get_full_name() or user.username,
                    email=user.email,
                    user=user,
                    # Bug fix: this never set company, so an Employee created this way was
                    # invisible to any company-scoped query (Company Admin's employee list,
                    # attendance, leave, payroll...) even though the link itself "worked".
                    company=get_user_company_or_default(user),
                )
                if employee.company_id is None:
                    self.stdout.write(self.style.WARNING(
                        f"Could not determine a company for '{user.username}' — created Employee "
                        f"#{employee.id} with no company set. It won't show up in any Company "
                        f"Admin's employee list until company is set manually."
                    ))
                self.stdout.write(self.style.SUCCESS(
                    f"Created Employee #{employee.id} ({employee.full_name}) and linked to user '{user.username}' (id={user.id})."
                ))
                return
            raise CommandError(
                f"No Employee record matches user '{user.username}' ({user.email}). "
                f"Pass --employee <code-or-id-or-name> to target one explicitly, "
                f"or --create to make a new record."
            )

        if employee.user_id == user.id:
            self.stdout.write(self.style.SUCCESS(
                f"Employee #{employee.id} ({employee.full_name}) is already linked to user '{user.username}' (id={user.id}). No change made."
            ))
            return

        if employee.user_id and not opts['force']:
            raise CommandError(
                f"Employee #{employee.id} ({employee.full_name}) is already linked to a different "
                f"user (user_id={employee.user_id}). Pass --force to overwrite."
            )

        employee.user = user
        employee.save(update_fields=['user'])
        self.stdout.write(self.style.SUCCESS(
            f"Linked Employee #{employee.id} ({employee.full_name}) -> user '{user.username}' (id={user.id})."
        ))

    def _resolve_employee(self, user, employee_ident):
        if employee_ident:
            qs = Employee.objects.filter(code__iexact=employee_ident)
            if not qs.exists() and employee_ident.isdigit():
                qs = Employee.objects.filter(id=int(employee_ident))
            if not qs.exists():
                qs = Employee.objects.filter(full_name__iexact=employee_ident)
            count = qs.count()
            if count == 0:
                raise CommandError(f"No employee found matching '{employee_ident}' (checked code, id, full name).")
            if count > 1:
                names = ', '.join(f"#{e.id} {e.full_name}" for e in qs)
                raise CommandError(f"Multiple employees match '{employee_ident}': {names}. Use --employee <id> instead.")
            return qs.first()

        if user.email:
            match = Employee.objects.filter(email__iexact=user.email).first()
            if match:
                return match
        match = Employee.objects.filter(full_name__iexact=user.username).first()
        if match:
            return match
        if user.first_name:
            match = Employee.objects.filter(full_name__iexact=user.first_name).first()
            if match:
                return match
        return None

    @staticmethod
    def _gen_code():
        from apps.hr.serializers import _gen_code
        return _gen_code(Employee, 'EMP')


def models_q_username_or_email(ident):
    from django.db.models import Q
    return Q(username__iexact=ident) | Q(email__iexact=ident)
