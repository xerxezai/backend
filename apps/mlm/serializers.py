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
    # Not required from the client — manually-added commissions (via the Commissions page's
    # "Add Commission" form) don't collect a rate, it's derived from MLMSettings by level.
    rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)

    class Meta:
        model = Commission
        fields = '__all__'

    def create(self, validated_data):
        if not validated_data.get('rate'):
            settings_obj = MLMSettings.get_solo()
            rate_by_level = {1: settings_obj.level1_rate, 2: settings_obj.level2_rate, 3: settings_obj.level3_rate}
            validated_data['rate'] = rate_by_level.get(validated_data.get('level'), 0)
        commission = super().create(validated_data)
        # Matches CommissionViewSet.calculate's behavior: a commission always adds to the
        # earning distributor's running total, regardless of pending/paid status.
        distributor = commission.distributor
        distributor.total_earnings = distributor.total_earnings + commission.amount
        distributor.save(update_fields=['total_earnings'])
        return commission


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
