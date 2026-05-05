"""
WSGI config for SEOZ Backend
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'seoz_backend.settings')

application = get_wsgi_application()