import re

from rest_framework import serializers

from apps.core.sanitize import clean_text
from .models import Affiliate, AffiliateCommission


class AffiliateApplySerializer(serializers.ModelSerializer):
    class Meta:
        model = Affiliate
        fields = [
            'full_name', 'email', 'affiliate_code', 'company_name',
            'website', 'promotion_method', 'audience_size',
        ]

    def validate_full_name(self, value):
        return clean_text(value)

    def validate_company_name(self, value):
        return clean_text(value)

    def validate_promotion_method(self, value):
        return clean_text(value)

    def validate_affiliate_code(self, value):
        code = value.strip().upper()
        if not re.match(r'^[A-Z0-9]{3,20}$', code):
            raise serializers.ValidationError('Use 3-20 letters/numbers only, e.g. LINUXFOUNDATION.')
        if Affiliate.objects.filter(affiliate_code=code).exists():
            raise serializers.ValidationError('This affiliate code is already taken.')
        return code


class AffiliateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Affiliate
        fields = [
            'id', 'full_name', 'email', 'affiliate_code', 'company_name', 'website',
            'promotion_method', 'audience_size', 'status', 'rejection_reason',
            'commission_rate', 'total_clicks', 'total_conversions', 'total_earnings',
            'bank_details', 'created_at', 'approved_at',
        ]
        read_only_fields = [
            'id', 'status', 'rejection_reason', 'commission_rate',
            'total_clicks', 'total_conversions', 'total_earnings', 'created_at', 'approved_at',
        ]


class AffiliateAdminListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Affiliate
        fields = [
            'id', 'full_name', 'email', 'affiliate_code', 'company_name', 'website',
            'promotion_method', 'audience_size', 'status', 'commission_rate',
            'total_clicks', 'total_conversions', 'total_earnings', 'created_at',
        ]


class AffiliateCommissionSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = AffiliateCommission
        fields = [
            'id', 'course', 'course_title', 'course_price', 'commission_rate',
            'commission_amount', 'status', 'paid_at', 'created_at',
        ]


class AffiliateCommissionAdminSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    affiliate_name = serializers.CharField(source='affiliate.full_name', read_only=True)
    affiliate_code = serializers.CharField(source='affiliate.affiliate_code', read_only=True)

    class Meta:
        model = AffiliateCommission
        fields = [
            'id', 'affiliate', 'affiliate_name', 'affiliate_code', 'course', 'course_title',
            'course_price', 'commission_rate', 'commission_amount', 'status', 'paid_at', 'created_at',
        ]
