import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('sales', '0002_quotationitem_product_salesorder_salesperson_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # This app is being fully replaced (see project notes): the old mlm_commission table
        # (from the previous MLMProfile/CommissionStructure/Transaction/Commission/Earning
        # design) is being superseded by a new, incompatible Commission model that reuses the
        # same table name. Verified empty (0 rows) before this migration was written, so it's
        # safe to drop here as part of the standard migration flow rather than out-of-band SQL.
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS mlm_commission CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name='Distributor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('distributor_id', models.CharField(help_text='e.g. DIST-001', max_length=20, unique=True)),
                ('name', models.CharField(max_length=150)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=40)),
                ('level', models.PositiveSmallIntegerField(default=1, help_text='1, 2 or 3 — computed from sponsor.level + 1, capped at 3')),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active', max_length=10)),
                ('joining_date', models.DateField(default=django.utils.timezone.localdate)),
                ('total_sales', models.DecimalField(decimal_places=2, default=0, help_text='Denormalized — updated when commissions are calculated', max_digits=14)),
                ('total_earnings', models.DecimalField(decimal_places=2, default=0, help_text="Denormalized sum of this distributor's commission amounts", max_digits=14)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sponsor', models.ForeignKey(blank=True, help_text='Who referred this distributor; null = root/top-level', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='downline', to='mlm.distributor')),
                ('user', models.ForeignKey(blank=True, help_text='Optional login account — not every distributor row needs one', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='distributor_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MLMSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level1_rate', models.DecimalField(decimal_places=2, default=10.00, max_digits=5)),
                ('level2_rate', models.DecimalField(decimal_places=2, default=5.00, max_digits=5)),
                ('level3_rate', models.DecimalField(decimal_places=2, default=2.00, max_digits=5)),
            ],
            options={
                'verbose_name': 'MLM Settings',
                'verbose_name_plural': 'MLM Settings',
            },
        ),
        migrations.CreateModel(
            name='Payout',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('payout_date', models.DateField()),
                ('method', models.CharField(choices=[('bank', 'Bank'), ('upi', 'UPI'), ('cash', 'Cash')], default='bank', max_length=10)),
                ('reference_number', models.CharField(blank=True, max_length=100)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed')], default='pending', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('distributor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payouts', to='mlm.distributor')),
            ],
            options={
                'ordering': ['-payout_date', '-id'],
            },
        ),
        migrations.CreateModel(
            name='Commission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.PositiveSmallIntegerField(help_text="1, 2 or 3 — how many levels above the order's originating distributor this earner sits")),
                ('rate', models.DecimalField(decimal_places=2, help_text='Percentage, e.g. 10.00', max_digits=5)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid')], default='pending', max_length=10)),
                ('created_date', models.DateTimeField(auto_now_add=True)),
                ('distributor', models.ForeignKey(help_text='The earner', on_delete=django.db.models.deletion.CASCADE, related_name='commissions', to='mlm.distributor')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mlm_commissions', to='sales.salesorder')),
            ],
            options={
                'ordering': ['-created_date'],
            },
        ),
    ]
