"""
ASGI config for XERXEZ Backend
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xerxez_backend.settings')

application = get_asgi_application()