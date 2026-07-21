from rest_framework import serializers

from .models import PartnerApplication


class PartnerApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerApplication
        fields = [
            'full_name', 'email', 'phone', 'linkedin_url', 'country', 'city', 'languages',
            'current_profession', 'years_experience', 'industries', 'estimated_deals',
            'network_description', 'agreed_to_nda',
        ]

    def validate_network_description(self, value):
        if len(value.strip()) < 100:
            raise serializers.ValidationError('Please describe your network in at least 100 characters.')
        return value

    def validate_agreed_to_nda(self, value):
        if not value:
            raise serializers.ValidationError('You must agree to maintain confidentiality to apply.')
        return value

    def validate_languages(self, value):
        if not value:
            raise serializers.ValidationError('Select at least one language.')
        return value

    def validate_industries(self, value):
        if not value:
            raise serializers.ValidationError('Select at least one industry.')
        return value


class PartnerApplicationSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = PartnerApplication
        fields = [
            'id', 'full_name', 'email', 'phone', 'linkedin_url', 'country', 'city', 'languages',
            'current_profession', 'years_experience', 'industries', 'estimated_deals',
            'network_description', 'agreed_to_nda', 'status', 'reviewed_by', 'reviewed_by_name',
            'reviewed_at', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'reviewed_by', 'reviewed_at']
