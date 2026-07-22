from rest_framework import serializers
from .models import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = '__all__'
        # Inquiry-management fields are admin-only (see ContactInquirySerializer) — never
        # writable from the public contact form, regardless of what a POST body contains.
        read_only_fields = ['id', 'created_at', 'status', 'assigned_to', 'priority', 'notes', 'replied_at', 'updated_at']


class ContactInquirySerializer(serializers.ModelSerializer):
    """Admin (super_admin-only) view/update of a contact inquiry."""
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True, default=None)

    class Meta:
        model = ContactMessage
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
