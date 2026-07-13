from rest_framework import serializers
from .models import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'full_name', 'email', 'phone', 'company',
                  'service', 'urgency', 'subject', 'message',
                  'country', 'plan_interest', 'team_size',
                  'budget_currency', 'budget_range', 'hear_about_us',
                  'created_at']
        read_only_fields = ['id', 'created_at']
