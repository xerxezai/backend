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


_REPEATED_CHAR_RE = re.compile(r'(.)\1{2,}')
_VOWEL_RE = re.compile(r'[aeiouAEIOU]')


def validate_human_name(value):
    """Rejects blank/whitespace-only entries, names under 3 characters, and strings
    that look like random keyboard input (no vowels at all, or the same character
    repeated 3+ times) rather than an actual name — e.g. "ghg", "vcxbv", "jjjj",
    "lllll". Attached directly to model CharFields (see validate_phone_with_country_code)
    so it's enforced everywhere a name is entered, not just one form.

    This is a heuristic, not a dictionary lookup — it won't catch every possible
    junk string (a few genuine short/unusual names could theoretically be flagged),
    but it stops the obvious keyboard-mash entries.
    """
    if not value:
        return
    stripped = value.strip()
    if len(stripped) < 3:
        raise ValidationError('Please enter at least 3 characters.')
    letters = re.sub(r'[^a-zA-Z]', '', stripped)
    if letters and not _VOWEL_RE.search(letters):
        raise ValidationError('This does not look like a real name — please check for typos.')
    if _REPEATED_CHAR_RE.search(stripped):
        raise ValidationError('This does not look like a real name — please check for typos.')
