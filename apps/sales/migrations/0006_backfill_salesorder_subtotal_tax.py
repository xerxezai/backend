from decimal import Decimal

from django.db import migrations

GST_RATE = Decimal('0.18')


def backfill(apps, schema_editor):
    """Backfills subtotal/tax on existing SalesOrder rows without ever touching the
    stored `total` — retroactively changing an already-issued order/invoice total is
    a business decision, not something a migration should do silently.

    - Orders with line items: historically recalc() applied no GST, so `total` already
      equals the raw item sum. subtotal=total, tax=0 honestly reflects that no tax was
      actually charged on these — it does not invent a tax split that was never applied.
    - Orders with no items (e.g. converted from a quotation before this fix copied line
      items over): `total` was copied from the quotation's own GST-inclusive total, so it
      already includes 18% GST with no visible subtotal — reverse-derive subtotal/tax from
      it so it's now consistent with SalesOrder.recalc()'s formula (subtotal * 1.18 = total).
    """
    SalesOrder = apps.get_model('sales', 'SalesOrder')
    for order in SalesOrder.objects.all():
        total = order.total or Decimal('0')
        if order.items.exists():
            order.subtotal = total
            order.tax = Decimal('0')
        else:
            subtotal = (total / (Decimal('1') + GST_RATE)).quantize(Decimal('0.01'))
            order.subtotal = subtotal
            order.tax = total - subtotal
        order.save(update_fields=['subtotal', 'tax'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0005_salesorder_subtotal_salesorder_tax'),
    ]

    operations = [
        migrations.RunPython(backfill, noop_reverse),
    ]
