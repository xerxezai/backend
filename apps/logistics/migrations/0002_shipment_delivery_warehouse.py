# Hand-written (see comment in views.py task notes): makemigrations' autodetector scans
# every installed app's live model state, not just the target app, so running it while
# apps.mlm.models was mid-edit by a parallel workstream triggered unrelated interactive
# rename prompts for mlm.Commission. Writing this migration directly avoids that race.
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logistics', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='shipment_number',
            field=models.CharField(default='', help_text='e.g. SHP-001', max_length=20, unique=True),
            preserve_default=False,
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
