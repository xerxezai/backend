# Hand-written (autodetector was blocked by an unrelated pending migration in another
# in-progress app — apps.logistics — during parallel development; this migration reflects
# exactly the Expense/TaxReport models added to apps/accounting/models.py).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expense_number', models.CharField(help_text='e.g. EXP-001', max_length=20, unique=True)),
                ('category', models.CharField(help_text='Free text, e.g. "Travel", "Office Supplies"', max_length=100)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('date', models.DateField()),
                ('description', models.CharField(blank=True, max_length=255)),
                ('paid_by', models.CharField(blank=True, help_text='Free-text name of who paid', max_length=150)),
                ('receipt_image', models.ImageField(blank=True, null=True, upload_to='receipts/')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-date', '-id'],
            },
        ),
        migrations.CreateModel(
            name='TaxReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('period', models.CharField(help_text='e.g. "2026-07" (monthly) or "2026-Q3" (quarterly)', max_length=20)),
                ('total_revenue', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('total_tax_collected', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('total_tax_paid', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('net_tax', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-period'],
            },
        ),
    ]
