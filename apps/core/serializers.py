from rest_framework import serializers

from .sanitize import clean_text


class SanitizedModelSerializer(serializers.ModelSerializer):
    """ModelSerializer that strips HTML/script markup from every string field
    on the way in — the serializer-level equivalent of calling clean_text()
    on each field by hand. Used by every public-facing free-text form (contact,
    careers, CRM) so a submitted name/message/note can never carry markup into
    the database. Non-string values (numbers, files, nested data) pass through
    untouched."""

    def to_internal_value(self, data):
        validated = super().to_internal_value(data)
        for key, value in validated.items():
            if isinstance(value, str):
                validated[key] = clean_text(value)
        return validated
