import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xerxez_backend.settings')

from django.contrib.auth import get_user_model
from apps.lma.models import LMAProfile

User = get_user_model()

# Update Danish
danish, _ = User.objects.get_or_create(username='Danish')
danish.email = 'danish@xerxez.com'
danish.set_password('[REDACTED]')
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
print('Danish updated: email=danish@xerxez.com password=[REDACTED] role=instructor')

# Update Tanzeem
tanzeem, _ = User.objects.get_or_create(username='Tanzeem')
tanzeem.email = 'tanzeem@xerxez.com'
tanzeem.set_password('[REDACTED]')
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
print('Tanzeem updated: email=tanzeem@xerxez.com password=[REDACTED] role=instructor')

print('Done! Both accounts ready for LMA login.')
