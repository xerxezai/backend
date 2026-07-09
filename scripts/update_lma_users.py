import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xerxez_backend.settings')

from django.contrib.auth import get_user_model
from apps.lma.models import LMAProfile

User = get_user_model()

PASSWORD = os.environ.get('LMA_USER_PASSWORD') or os.environ.get('DJANGO_SUPERUSER_PASSWORD')
if not PASSWORD:
    raise SystemExit('Set the LMA_USER_PASSWORD (or DJANGO_SUPERUSER_PASSWORD) environment variable first.')

# Update Danish
danish, _ = User.objects.get_or_create(username='Danish')
danish.email = 'danish@xerxez.com'
danish.set_password(PASSWORD)
danish.first_name = 'Danish'
danish.is_staff = True
danish.is_active = True
danish.role = 'admin'
danish.save()

danish_lma, _ = LMAProfile.objects.get_or_create(user=danish)
danish_lma.lma_role = 'instructor'
danish_lma.can_access_student = True
danish_lma.can_access_instructor = True
danish_lma.save()
print('Danish updated: email=danish@xerxez.com role=instructor')

# Update Tanzeem
tanzeem, _ = User.objects.get_or_create(username='Tanzeem')
tanzeem.email = 'tanzeem@xerxez.com'
tanzeem.set_password(PASSWORD)
tanzeem.first_name = 'Tanzeem'
tanzeem.is_staff = True
tanzeem.is_active = True
tanzeem.role = 'manager'
tanzeem.save()

tanzeem_lma, _ = LMAProfile.objects.get_or_create(user=tanzeem)
tanzeem_lma.lma_role = 'instructor'
tanzeem_lma.can_access_student = True
tanzeem_lma.can_access_instructor = True
tanzeem_lma.save()
print('Tanzeem updated: email=tanzeem@xerxez.com role=instructor')

print('Done! Both accounts ready for LMA login.')
