"""
Initial migration for the custom auth system.
Creates EmailAddress and SocialAccount tables.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailAddress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('verified', models.BooleanField(default=False)),
                ('primary', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_addresses', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'dp_auth_email_address',
                'verbose_name_plural': 'email addresses',
                'unique_together': {('user', 'email')},
            },
        ),
        migrations.CreateModel(
            name='SocialAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('google', 'Google'), ('apple', 'Apple')], max_length=30)),
                ('uid', models.CharField(max_length=255)),
                ('extra_data', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_login', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='social_accounts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'dp_auth_social_account',
                'unique_together': {('provider', 'uid')},
            },
        ),
        migrations.AddIndex(
            model_name='socialaccount',
            index=models.Index(fields=['user', 'provider'], name='dp_auth_soc_user_id_331db1_idx'),
        ),
    ]
