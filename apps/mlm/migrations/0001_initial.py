import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    # Deliberately depends on AUTH_USER_MODEL only, matching exactly what production already
    # has recorded for 'mlm.0001_initial' from before this app's schema was rewritten (see
    # project notes / feedback_migration_rewrites_are_dangerous). The Commission model — which
    # needs a dependency on 'sales' for its order FK — lives in 0002 instead, where declaring a
    # new dependency is safe: 0002 is a migration name that was never previously applied
    # anywhere, so it can't create the kind of history-order conflict a same-named-but-rewritten
    # 0001 did (InconsistentMigrationHistory: mlm.0001 recorded as applied before a 'sales'
    # migration that didn't exist yet at that time).
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
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
    ]
