"""
Additive migration: adds status to Attendance, creates Shift, SalaryStructure, Payroll, PaySlip.
No existing columns or tables are dropped.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add status to existing Attendance (safe, has default)
        migrations.AddField(
            model_name='attendance',
            name='status',
            field=models.CharField(
                blank=True,
                choices=[('present', 'Present'), ('absent', 'Absent'), ('late', 'Late'), ('half_day', 'Half Day')],
                default='present',
                max_length=20,
            ),
        ),

        # Shift model
        migrations.CreateModel(
            name='Shift',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('employees', models.ManyToManyField(blank=True, related_name='shifts', to='hr.employee')),
            ],
        ),

        # SalaryStructure model
        migrations.CreateModel(
            name='SalaryStructure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('basic_salary', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('allowances', models.JSONField(blank=True, default=dict)),
                ('deductions', models.JSONField(blank=True, default=dict)),
                ('effective_date', models.DateField()),
                ('employee', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='salary_structure', to='hr.employee')),
            ],
        ),

        # Payroll model
        migrations.CreateModel(
            name='Payroll',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.PositiveSmallIntegerField()),
                ('year', models.PositiveSmallIntegerField()),
                ('working_days', models.PositiveSmallIntegerField(default=0)),
                ('present_days', models.PositiveSmallIntegerField(default=0)),
                ('basic', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('allowances', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('deductions', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('gross', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('net_salary', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('status', models.CharField(
                    choices=[('draft', 'Draft'), ('approved', 'Approved'), ('paid', 'Paid')],
                    default='draft', max_length=20,
                )),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payrolls', to='hr.employee')),
                ('generated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_payrolls', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-year', '-month'],
            },
        ),
        migrations.AddConstraint(
            model_name='payroll',
            constraint=models.UniqueConstraint(fields=['employee', 'month', 'year'], name='unique_payroll_per_employee_month'),
        ),

        # PaySlip model
        migrations.CreateModel(
            name='PaySlip',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pdf_ref', models.CharField(blank=True, max_length=255)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('payroll', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='payslip', to='hr.payroll')),
            ],
        ),
    ]
