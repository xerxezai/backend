from decimal import Decimal

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
    order_customer_name = serializers.CharField(source='order.customer.name', read_only=True, default=None)
    order_amount = serializers.DecimalField(source='order.total', max_digits=14, decimal_places=2, read_only=True, default=None)
    # Not required from the client — manually-added commissions (via the Commissions page's
    # "Add Commission" form) don't collect a rate, it's derived from MLMSettings by level.
    rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    # Not required either when a sales order is linked — amount is then derived server-side
    # from that order's total, so a client-supplied figure can never drift from it. Still
    # required for a free-standing manual commission with no order to derive from.
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)

    class Meta:
        model = Commission
        fields = '__all__'

    def create(self, validated_data):
        if not validated_data.get('rate'):
            settings_obj = MLMSettings.get_solo()
            rate_by_level = {1: settings_obj.level1_rate, 2: settings_obj.level2_rate, 3: settings_obj.level3_rate}
            validated_data['rate'] = rate_by_level.get(validated_data.get('level'), 0)
        order = validated_data.get('order')
        if order is not None:
            # Server-computed, always — a client-sent amount for an order-linked commission
            # is never trusted, so the two can't disagree with the order it's traceable to.
            validated_data['amount'] = (order.total or Decimal('0')) * (validated_data['rate'] / Decimal('100'))
        elif validated_data.get('amount') is None:
            raise serializers.ValidationError({'amount': 'Amount is required when no sales order is linked.'})
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
