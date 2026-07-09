"""Strip HTML/script markup from user-supplied free-text fields.

All of these fields are stored and rendered as plain text, so no tags
are allowed at all.
"""
import bleach


def clean_text(value):
    if not isinstance(value, str):
        return value
    return bleach.clean(value, tags=[], strip=True)
