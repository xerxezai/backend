"""
Seed ERP admin accounts.
Requires the DJANGO_SUPERUSER_PASSWORD environment variable.
Run: python manage.py shell < scripts/seed_admins.py
"""

import os

from django.contrib.auth import get_user_model
from apps.users.models import UserProfile

User = get_user_model()

PASSWORD = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
if not PASSWORD:
    raise SystemExit("Set the DJANGO_SUPERUSER_PASSWORD environment variable first.")

ACCOUNTS = [
    {"username": "Tanzeem", "role": "manager", "first_name": "Tanzeem", "is_staff": True},
    {"username": "Danish",  "role": "admin",   "first_name": "Danish",  "is_staff": True},
]

for acc in ACCOUNTS:
    user, created = User.objects.get_or_create(username=acc["username"])
    user.set_password(PASSWORD)
    user.first_name = acc["first_name"]
    user.is_staff   = acc["is_staff"]
    user.save()

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = acc["role"]
    profile.save()

    action = "Created" if created else "Updated"
    print(f"✓ {action}: {acc['username']} (role={acc['role']})")

print("\nSeed complete.")
