from decimal import Decimal
from django.db import transaction
from rest_framework import serializers
from .models import Quotation, QuotationItem, SalesOrder, SalesOrderItem


def _build_items(model, fk_field, parent, items_data):
    """Builds unsaved line-item instances for bulk_create. bulk_create skips each
    instance's save(), so line_total/description are computed here to mirror
    QuotationItem.save()/SalesOrderItem.save() exactly."""
    items = []
    for item in items_data:
        obj = model(**{fk_field: parent}, **item)
        if not obj.description and obj.product_id:
            obj.description = obj.product.name
        obj.line_total = (obj.quantity or 0) * (obj.unit_price or 0)
        items.append(obj)
    return items


class QuotationItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)

    class Meta:
        model = QuotationItem
        fields = ['id', 'quotation', 'product', 'product_name', 'description', 'quantity', 'unit_price', 'line_total']
        read_only_fields = ['id', 'line_total']
        extra_kwargs = {'quotation': {'required': False}}


class QuotationSerializer(serializers.ModelSerializer):
    items = QuotationItemSerializer(many=True, required=False)
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = Quotation
        fields = '__all__'
        read_only_fields = ['subtotal', 'tax', 'total']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        with transaction.atomic():
            quotation = Quotation.objects.create(**validated_data)
            QuotationItem.objects.bulk_create(_build_items(QuotationItem, 'quotation', quotation, items_data))
            quotation.recalc()
            quotation.save()
        return quotation

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            if items_data is not None:
                instance.items.all().delete()
                QuotationItem.objects.bulk_create(_build_items(QuotationItem, 'quotation', instance, items_data))
            instance.recalc()
            instance.save()
        return instance


class SalesOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)

    class Meta:
        model = SalesOrderItem
        fields = ['id', 'order', 'product', 'product_name', 'description', 'quantity', 'unit_price', 'line_total']
        read_only_fields = ['id', 'line_total']
        extra_kwargs = {'order': {'required': False}}


class SalesOrderSerializer(serializers.ModelSerializer):
    items = SalesOrderItemSerializer(many=True, required=False)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    quotation_number = serializers.CharField(source='quotation.number', read_only=True, default=None)
    salesperson_name = serializers.SerializerMethodField()
    distributor_name = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()
    invoice_status = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrder
        fields = '__all__'
        read_only_fields = ['subtotal', 'tax', 'total', 'created_by']

    def create(self, validated_data):
        items_data = validated_data.pop('items', None)
        with transaction.atomic():
            order = SalesOrder.objects.create(**validated_data)
            if items_data:
                SalesOrderItem.objects.bulk_create(_build_items(SalesOrderItem, 'order', order, items_data))
                order.recalc()
                order.save()
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            if items_data is not None:
                instance.items.all().delete()
                SalesOrderItem.objects.bulk_create(_build_items(SalesOrderItem, 'order', instance, items_data))
                instance.recalc()
                instance.save()
        return instance

    def get_salesperson_name(self, obj):
        if not obj.salesperson_id:
            return None
        return obj.salesperson.get_full_name() or obj.salesperson.username

    def get_distributor_name(self, obj):
        if not obj.distributor_id:
            return None
        return f'{obj.distributor.name} ({obj.distributor.distributor_id})'

    def get_invoice_number(self, obj):
        invoice = obj.invoices.order_by('-issue_date').first()
        return invoice.number if invoice else None

    def get_invoice_status(self, obj):
        """Derived from invoices linked to this order — never stored, so it can't drift out
        of sync with the invoicing app's own Invoice.total (mirrors sync_invoice_payment_status's
        same reasoning for amount_paid/status on Invoice)."""
        invoiced = sum((inv.total for inv in obj.invoices.all()), Decimal('0'))
        if invoiced <= 0:
            return 'not_invoiced'
        if invoiced < (obj.total or Decimal('0')):
            return 'partial'
        return 'fully_invoiced'

    def get_payment_status(self, obj):
        invoices = list(obj.invoices.all())
        invoiced = sum((inv.total for inv in invoices), Decimal('0'))
        paid = sum((inv.amount_paid for inv in invoices), Decimal('0'))
        if paid <= 0:
            return 'unpaid'
        if paid < invoiced:
            return 'partial'
        return 'paid'
