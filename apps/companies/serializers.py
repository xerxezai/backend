from rest_framework import serializers

from .models import Company, CompanyUser


class CompanySerializer(serializers.ModelSerializer):
    user_count = serializers.SerializerMethodField()

    def get_user_count(self, obj):
        return obj.company_users.filter(is_active=True).count()

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'slug', 'industry', 'country', 'city', 'phone', 'email',
            'website', 'status', 'plan', 'trial_ends_at', 'user_count', 'created_at',
        ]


class CompanyUserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    class Meta:
        model = CompanyUser
        fields = ['id', 'username', 'email', 'full_name', 'role', 'is_active', 'joined_at']
