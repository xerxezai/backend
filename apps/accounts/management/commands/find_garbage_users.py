from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError

from apps.core.validators import validate_human_name


class Command(BaseCommand):
    help = (
        "Finds active users whose first/last name (or username, when both are blank) "
        "looks like keyboard-mash junk rather than a real name -- e.g. the 'ghg', "
        "'vcxbv', 'jjjj', 'lllll' entries polluting the Salesperson dropdown. "
        "Dry-run by default: only lists what it finds. Pass --deactivate to set "
        "is_active=False on the matches (reversible via Django admin), which removes "
        "them from the Salesperson dropdown without deleting the account or anything "
        "it's linked to."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--deactivate', action='store_true',
            help='Set is_active=False on every flagged user instead of just listing them.',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        flagged = []
        for user in User.objects.filter(is_active=True).order_by('username'):
            display_name = f'{user.first_name} {user.last_name}'.strip() or user.username
            bad_fields = []
            for field_name, value in (('first_name', user.first_name), ('last_name', user.last_name), ('username', user.username)):
                if not value:
                    continue
                try:
                    validate_human_name(value)
                except ValidationError:
                    bad_fields.append(f'{field_name}="{value}"')
            if bad_fields:
                flagged.append((user, display_name, bad_fields))

        if not flagged:
            self.stdout.write(self.style.SUCCESS('No garbage-looking users found.'))
            return

        self.stdout.write(f'Found {len(flagged)} user(s) that look like junk:\n')
        for user, display_name, bad_fields in flagged:
            self.stdout.write(f'  id={user.id:<5} "{display_name}" -- {", ".join(bad_fields)}')

        if options['deactivate']:
            ids = [u.id for u, _, _ in flagged]
            User.objects.filter(id__in=ids).update(is_active=False)
            self.stdout.write(self.style.WARNING(f'\nDeactivated {len(ids)} user(s). They no longer appear in the Salesperson dropdown.'))
        else:
            self.stdout.write(self.style.WARNING('\nDry run only -- re-run with --deactivate to actually deactivate these accounts.'))
