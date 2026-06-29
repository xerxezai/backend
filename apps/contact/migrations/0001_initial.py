from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ContactMessage',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name',  models.CharField(max_length=200)),
                ('email',      models.EmailField(max_length=254)),
                ('phone',      models.CharField(blank=True, max_length=50)),
                ('company',    models.CharField(blank=True, max_length=200)),
                ('service',    models.CharField(blank=True, max_length=200)),
                ('urgency',    models.CharField(choices=[('normal', 'Normal'), ('urgent', 'Urgent'), ('critical', 'Critical')], default='normal', max_length=20)),
                ('subject',    models.CharField(blank=True, max_length=300)),
                ('message',    models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_read',    models.BooleanField(default=False)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
