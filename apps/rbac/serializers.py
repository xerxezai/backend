from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Module, UserModuleAccess, AccessRequest

User = get_user_model()


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'name', 'display_name', 'icon', 'order', 'is_active']


class UserModuleAccessSerializer(serializers.ModelSerializer):
    module_name = serializers.CharField(source='module.name', read_only=True)
    module_display = serializers.CharField(source='module.display_name', read_only=True)

    class Meta:
        model = UserModuleAccess
        fields = ['id', 'module_name', 'module_display', 'role', 'granted_at', 'is_active']


class UserListSerializer(serializers.ModelSerializer):
    module_access = UserModuleAccessSerializer(many=True, read_only=True)
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'full_name', 'is_active', 'is_superuser', 'module_access', 'date_joined']


class CreateUserSerializer(serializers.Serializer):
    full_name = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=['super_admin', 'module_admin', 'regular_user', 'read_only'])
    modules = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('A user with that username already exists.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with that email already exists.')
        return value


class AccessRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    module_name = serializers.CharField(source='module.display_name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.username', read_only=True, default=None)

    class Meta:
        model = AccessRequest
        fields = ['id', 'user_name', 'module_name', 'reason', 'status', 'reviewed_by_name', 'reviewed_at', 'created_at']
