from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='OTPToken',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email',       models.EmailField(db_index=True, max_length=254)),
                ('otp',         models.CharField(max_length=6)),
                ('reset_token', models.CharField(blank=True, db_index=True, max_length=64)),
                ('created_at',  models.DateTimeField(auto_now_add=True)),
                ('expires_at',  models.DateTimeField()),
                ('is_used',     models.BooleanField(default=False)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
