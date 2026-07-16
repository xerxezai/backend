"""Shared field validators used across apps (contact, crm, hr, careers, accounts, ...)."""
import re

from django.core.exceptions import ValidationError

PHONE_RE = re.compile(r'^\+\d{8,15}$')


def validate_phone_with_country_code(value):
    """A phone number stored with its country code, e.g. "+971501234567".

    Must start with "+" and have 8-15 digits total after it. Attached directly
    to model CharFields so every serializer built from that model (ModelSerializer
    with `fields = '__all__'` or an explicit field list) enforces it automatically.
    """
    if not value:
        return
    if not PHONE_RE.match(value):
        raise ValidationError('Please enter a valid phone number with country code')
