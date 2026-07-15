from decimal import Decimal

from django.db import migrations
from django.db.models import Sum


def delete_zero_amount_commissions(apps, schema_editor):
    """One-time cleanup: zero-amount commissions should never have existed (see
    generate_commission_for_order's zero-total guard, added alongside this migration) —
    remove any that were created before that guard existed, then re-sync the affected
    distributors' denormalized total_earnings/total_sales from what's left."""
    Commission = apps.get_model('mlm', 'Commission')
    Distributor = apps.get_model('mlm', 'Distributor')
    SalesOrder = apps.get_model('sales', 'SalesOrder')

    affected_distributor_ids = set(
        Commission.objects.filter(amount=0).values_list('distributor_id', flat=True)
    )
    Commission.objects.filter(amount=0).delete()

    for distributor_id in affected_distributor_ids:
        earnings = Commission.objects.filter(distributor_id=distributor_id).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        sales = SalesOrder.objects.filter(distributor_id=distributor_id, status='confirmed').aggregate(t=Sum('total'))['t'] or Decimal('0')
        Distributor.objects.filter(pk=distributor_id).update(total_earnings=earnings, total_sales=sales)


class Migration(migrations.Migration):

    dependencies = [
        ('mlm', '0004_commission_notes_alter_commission_order'),
    ]

    operations = [
        migrations.RunPython(delete_zero_amount_commissions, migrations.RunPython.noop),
    ]
