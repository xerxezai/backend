from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Supplier, PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem, Bill, next_number


def _build_po_items(po, items_data):
    """Builds unsaved PurchaseOrderItem instances for bulk_create. bulk_create skips
    each instance's save(), so total is computed here to mirror PurchaseOrderItem.save()."""
    items = []
    for item in items_data:
        obj = PurchaseOrderItem(purchase_order=po, **item)
        obj.total = (obj.quantity or 0) * (obj.unit_price or 0)
        items.append(obj)
    return items


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)

    class Meta:
        model = PurchaseOrderItem
        fields = ['id', 'purchase_order', 'product', 'product_name', 'quantity', 'unit_price', 'total']
        read_only_fields = ['id', 'total']
        extra_kwargs = {'purchase_order': {'required': False}}


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, required=False)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = '__all__'
        read_only_fields = ['po_number', 'total']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        with transaction.atomic():
            po = PurchaseOrder.objects.create(po_number=next_number(PurchaseOrder, 'po_number', 'PO'), **validated_data)
            PurchaseOrderItem.objects.bulk_create(_build_po_items(po, items_data))
            po.recalc()
            po.save()
        return po

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            if items_data is not None:
                instance.items.all().delete()
                PurchaseOrderItem.objects.bulk_create(_build_po_items(instance, items_data))
            instance.recalc()
            instance.save()
        return instance


class GoodsReceiptItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)

    class Meta:
        model = GoodsReceiptItem
        fields = ['id', 'goods_receipt', 'product', 'product_name', 'quantity_received']


class GoodsReceiptSerializer(serializers.ModelSerializer):
    # Items and stock movements are created server-side by the viewset (see
    # apps.procurement.views._create_goods_receipt) — read-only here so a client
    # can't bypass that path and desync inventory from what the receipt says.
    items = GoodsReceiptItemSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='purchase_order.supplier.name', read_only=True)
    po_number = serializers.CharField(source='purchase_order.po_number', read_only=True)
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True, default=None)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True, default=None)

    class Meta:
        model = GoodsReceipt
        fields = '__all__'
        read_only_fields = ['receipt_number', 'received_by']


class BillSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    po_number = serializers.CharField(source='purchase_order.po_number', read_only=True, default=None)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = '__all__'
        read_only_fields = ['bill_number']

    def get_is_overdue(self, obj):
        return bool(obj.status == 'unpaid' and obj.due_date and obj.due_date < timezone.now().date())

    def create(self, validated_data):
        validated_data['bill_number'] = next_number(Bill, 'bill_number', 'BILL')
        return super().create(validated_data)
