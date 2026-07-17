from django.db import migrations

# Duplicated from Shipment.STATUS (models.py) — migrations use a frozen historical
# model, so the real choices list isn't available here.
STATUS_LABELS = {
    'pending': 'Pending',
    'dispatched': 'Dispatched',
    'in_transit': 'In Transit',
    'delivered': 'Delivered',
    'returned': 'Returned',
    'cancelled': 'Cancelled',
}


def forwards(apps, schema_editor):
    TrackingUpdate = apps.get_model('logistics', 'TrackingUpdate')
    for status, label in STATUS_LABELS.items():
        TrackingUpdate.objects.filter(
            status=status, description=f'Status changed to {status}',
        ).update(description=f'Status changed to {label}')


def backwards(apps, schema_editor):
    TrackingUpdate = apps.get_model('logistics', 'TrackingUpdate')
    for status, label in STATUS_LABELS.items():
        TrackingUpdate.objects.filter(
            status=status, description=f'Status changed to {label}',
        ).update(description=f'Status changed to {status}')


class Migration(migrations.Migration):

    dependencies = [
        ('logistics', '0003_shipment_origin_warehouse_alter_shipment_origin'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
