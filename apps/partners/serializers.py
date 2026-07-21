from rest_framework import serializers

from .models import Partner, PartnerDeal


class PartnerApplySerializer(serializers.ModelSerializer):
    """Public application form — POST /partners/apply/. Creates a `Partner` row with
    status='pending'; nothing here is user-editable after submission except by admin."""

    class Meta:
        model = Partner
        fields = [
            'full_name', 'email', 'phone', 'linkedin_url', 'country', 'city', 'target_market', 'languages',
            'current_profession', 'years_experience', 'modules', 'estimated_deals',
            'network_description', 'agreed_to_nda',
        ]

    def validate_network_description(self, value):
        if len(value.strip()) < 20:
            raise serializers.ValidationError('Please describe your network in at least 20 characters.')
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
            raise serializers.ValidationError('Select at least one package.')
        return value


class PartnerSerializer(serializers.ModelSerializer):
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = Partner
        fields = [
            'id', 'full_name', 'email', 'phone', 'country', 'city', 'target_market', 'linkedin_url', 'languages',
            'current_profession', 'years_experience', 'modules', 'estimated_deals', 'network_description', 'agreed_to_nda',
            'commission_tier', 'status', 'partner_code', 'total_deals', 'total_commission_earned', 'total_commission_paid',
            'notes', 'joined_at', 'approved_by', 'approved_by_name', 'approved_at',
        ]
        read_only_fields = [
            'id', 'partner_code', 'total_deals', 'total_commission_earned', 'total_commission_paid',
            'joined_at', 'approved_by', 'approved_at',
        ]


class PartnerDealSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='partner.full_name', read_only=True)
    partner_code = serializers.CharField(source='partner.partner_code', read_only=True)

    class Meta:
        model = PartnerDeal
        fields = [
            'id', 'partner', 'partner_name', 'partner_code', 'deal_number',
            'client_company', 'client_contact_person', 'client_phone', 'client_email', 'client_country',
            'package', 'num_employees', 'current_system', 'notes',
            'status', 'deal_value', 'commission_rate', 'commission_amount', 'commission_status', 'commission_paid_at',
            'submitted_at', 'updated_at', 'reviewed_by',
        ]
        read_only_fields = [
            'id', 'partner', 'partner_name', 'partner_code', 'deal_number',
            'commission_amount', 'submitted_at', 'updated_at', 'reviewed_by',
        ]

    def validate_client_company(self, value):
        if not value.strip():
            raise serializers.ValidationError('Client company name is required.')
        return value
