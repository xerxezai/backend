from rest_framework import serializers

from .models import Asset, MaintenanceRecord, AssetDepreciation, next_number


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    asset_code = serializers.CharField(source='asset.asset_code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = MaintenanceRecord
        fields = '__all__'
        extra_kwargs = {'asset': {'required': False}, 'created_by': {'required': False}}


class AssetDepreciationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetDepreciation
        fields = '__all__'
        extra_kwargs = {'asset': {'required': False}}


class AssetSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True, default=None)
    maintenance_overdue = serializers.SerializerMethodField()
    qr_code_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = '__all__'
        read_only_fields = ['asset_code', 'qr_code', 'qr_code_image']

    def get_maintenance_overdue(self, obj):
        from django.utils import timezone
        return bool(obj.next_maintenance and obj.next_maintenance < timezone.now().date())

    def get_qr_code_image_url(self, obj):
        if not obj.qr_code_image:
            return None
        request = self.context.get('request')
        url = obj.qr_code_image.url
        return request.build_absolute_uri(url) if request else url

    def create(self, validated_data):
        validated_data['asset_code'] = next_number(Asset, 'asset_code', 'AST')
        return super().create(validated_data)
