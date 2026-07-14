from rest_framework import serializers

from .models import Distributor, Commission, Payout, MLMSettings, next_number


class DistributorSerializer(serializers.ModelSerializer):
    sponsor_name = serializers.CharField(source='sponsor.name', read_only=True, default=None)
    sponsor_distributor_id = serializers.CharField(source='sponsor.distributor_id', read_only=True, default=None)
    downline_count = serializers.SerializerMethodField()

    class Meta:
        model = Distributor
        fields = '__all__'
        read_only_fields = ['distributor_id', 'level', 'total_sales', 'total_earnings']

    def get_downline_count(self, obj):
        return obj.downline.count()

    def create(self, validated_data):
        validated_data['distributor_id'] = next_number(Distributor, 'distributor_id', 'DIST')
        # level is computed server-side in Distributor.save() from the chosen sponsor
        return super().create(validated_data)


class CommissionSerializer(serializers.ModelSerializer):
    distributor_name = serializers.CharField(source='distributor.name', read_only=True)
    distributor_id_display = serializers.CharField(source='distributor.distributor_id', read_only=True)
    order_number = serializers.CharField(source='order.number', read_only=True, default=None)

    class Meta:
        model = Commission
        fields = '__all__'


class PayoutSerializer(serializers.ModelSerializer):
    distributor_name = serializers.CharField(source='distributor.name', read_only=True)

    class Meta:
        model = Payout
        fields = '__all__'
        read_only_fields = ['status']


class MLMSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLMSettings
        fields = ['level1_rate', 'level2_rate', 'level3_rate']
