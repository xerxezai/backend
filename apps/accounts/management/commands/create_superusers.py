"""
Deletes ALL existing users, then creates the two XERXEZ superuser accounts.
Run with:  python manage.py create_superusers
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models.signals import post_save

SUPERUSERS = [
    {
        "username":   "Tanzeem",
        "email":      "xerxez.in@gmail.com",
        "password":   "[REDACTED]",
        "first_name": "Tanzeem",
        "last_name":  "",
    },
    {
        "username":   "Danish",
        "email":      "danish@xerxez.com",
        "password":   "[REDACTED]",
        "first_name": "Danish",
        "last_name":  "",
    },
]


class Command(BaseCommand):
    help = "Wipe all users and create the two XERXEZ superuser accounts"

    def handle(self, *args, **kwargs):
        from apps.users.models import UserProfile, create_user_profile
        User = get_user_model()

        # ── 1. Delete all existing users (profiles cascade-delete) ──
        count = User.objects.count()
        User.objects.all().delete()
        self.stdout.write(self.style.WARNING(f"  [DELETED] {count} existing user(s)"))

        # ── 2. Reset the PK sequence ──
        table = User._meta.db_table
        with connection.cursor() as cur:
            cur.execute(f"""
                SELECT setval(
                    pg_get_serial_sequence('{table}', 'id'),
                    1,
                    false
                )
            """)

        # ── 3. Disconnect post_save signal to avoid stale-FK issues ──
        post_save.disconnect(create_user_profile, sender=User)

        try:
            for data in SUPERUSERS:
                user = User.objects.create_superuser(
                    username=data["username"],
                    email=data["email"],
                    password=data["password"],
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                )
                # Create profile manually; silently skip if local FK is stale
                try:
                    UserProfile.objects.get_or_create(user=user, defaults={"role": "admin"})
                except Exception:
                    pass

                self.stdout.write(self.style.SUCCESS(
                    f"  [CREATED] {data['username']}  |  email: {data['email']}  |  password: {data['password']}"
                ))
        finally:
            post_save.connect(create_user_profile, sender=User)

        self.stdout.write(self.style.SUCCESS(
            "\nDone. Login at /admin/ with either account."
        ))
