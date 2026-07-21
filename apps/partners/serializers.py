from rest_framework import serializers

from .models import PartnerApplication, PartnerLead


class PartnerApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerApplication
        fields = [
            'full_name', 'email', 'phone', 'linkedin_url', 'country', 'city', 'target_market', 'languages',
            'current_profession', 'years_experience', 'modules', 'estimated_deals',
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

    def validate_modules(self, value):
        if not value:
            raise serializers.ValidationError('Select at least one module.')
        return value


class PartnerApplicationSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = PartnerApplication
        fields = [
            'id', 'full_name', 'email', 'phone', 'linkedin_url', 'country', 'city', 'target_market', 'languages',
            'current_profession', 'years_experience', 'modules', 'estimated_deals',
            'network_description', 'agreed_to_nda', 'status', 'reviewed_by', 'reviewed_by_name',
            'reviewed_at', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'reviewed_by', 'reviewed_at']


class PartnerLeadSerializer(serializers.ModelSerializer):
    commission_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = PartnerLead
        fields = [
            'id', 'client_name', 'company', 'country', 'phone', 'email',
            'package', 'modules_needed', 'notes', 'deal_value', 'commission_amount',
            'status', 'created_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'commission_amount']

    def validate_client_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('Client name is required.')
        return value
