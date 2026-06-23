"""
MLM Serializers for XERXEZ Backend
"""

from rest_framework import serializers
from .models import MLMProfile, CommissionStructure, Transaction, Commission, Earning


class MLMProfileSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')
    email = serializers.ReadOnlyField(source='user.email')
    full_name = serializers.SerializerMethodField()
    referrer_username = serializers.SerializerMethodField()
    referrer_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = MLMProfile
        fields = [
            'id', 'username', 'email', 'full_name',
            'referrer_username', 'referrer_code',
            'referral_code', 'level', 'is_active',
            'joined_at', 'total_referrals',
        ]
        read_only_fields = ['id', 'referral_code', 'level', 'joined_at', 'total_referrals']

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_referrer_username(self, obj):
        return obj.referrer.user.username if obj.referrer else None


class CommissionStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionStructure
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class TransactionSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Transaction
        fields = [
            'id', 'username', 'amount', 'status',
            'description', 'reference', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'reference', 'created_at', 'updated_at']


class CommissionSerializer(serializers.ModelSerializer):
    earner_username = serializers.ReadOnlyField(source='earner.username')
    source_username = serializers.ReadOnlyField(source='source_user.username')
    transaction_reference = serializers.ReadOnlyField(source='transaction.reference')

    class Meta:
        model = Commission
        fields = [
            'id', 'earner_username', 'source_username',
            'transaction_reference', 'level',
            'commission_rate', 'amount', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EarningSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Earning
        fields = [
            'id', 'username',
            'total_earned', 'pending_earnings',
            'approved_earnings', 'paid_earnings',
            'last_payout', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']


class ReferralTreeNodeSerializer(serializers.ModelSerializer):
    """Recursive serializer for the referral tree — limits depth to avoid N+1."""
    username = serializers.ReadOnlyField(source='user.username')
    full_name = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = MLMProfile
        fields = [
            'id', 'username', 'full_name',
            'referral_code', 'level',
            'total_referrals', 'joined_at',
            'children',
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_children(self, obj):
        max_depth = self.context.get('max_depth', 3)
        current_depth = self.context.get('current_depth', 0)
        if current_depth >= max_depth - 1:
            return []
        child_context = {**self.context, 'current_depth': current_depth + 1}
        children = obj.referrals.filter(is_active=True).select_related('user')
        return ReferralTreeNodeSerializer(children, many=True, context=child_context).data
