# Hand-written (see comment in views.py task notes): makemigrations' autodetector scans
# every installed app's live model state, not just the target app, so running it while
# apps.mlm.models was mid-edit by a parallel workstream triggered unrelated interactive
# rename prompts for mlm.Commission. Writing this migration directly avoids that race.
#
# shipment_number is added in three steps (nullable -> backfill -> not-null) rather than a
# single AddField with a blank default, because Shipment is an existing, previously-linked
# table that may already have real rows on production — a single-step AddField with
# default='' would try to backfill every existing row with the same value, which violates
# the unique constraint the instant there's more than one row.
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def backfill_shipment_numbers(apps, schema_editor):
    Shipment = apps.get_model('logistics', 'Shipment')
    for shipment in Shipment.objects.order_by('id'):
        shipment.shipment_number = f'SHP-{shipment.id:03d}'
        shipment.save(update_fields=['shipment_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('logistics', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='shipment_number',
            field=models.CharField(help_text='e.g. SHP-001', max_length=20, null=True, unique=True),
        ),
        migrations.RunPython(backfill_shipment_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='shipment',
            name='shipment_number',
            field=models.CharField(help_text='e.g. SHP-001', max_length=20, unique=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='actual_delivery',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='Warehouse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('location', models.CharField(blank=True, max_length=255)),
                ('capacity', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('manager', models.CharField(blank=True, max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Delivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delivery_date', models.DateField()),
                ('delivered_by', models.CharField(blank=True, max_length=150)),
                ('signature', models.CharField(blank=True, help_text='Free-text signature capture (no file upload)', max_length=255)),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('delivered', 'Delivered'), ('failed', 'Failed'), ('partial', 'Partial')], default='delivered', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('shipment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deliveries', to='logistics.shipment')),
            ],
            options={
                'ordering': ['-delivery_date', '-id'],
            },
        ),
    ]
