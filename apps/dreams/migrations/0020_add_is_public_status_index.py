from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dreams', '0019_interactive_checkin_fields'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='dream',
            index=models.Index(fields=['is_public', 'status'], name='dreams_is_publ_1203f1_idx'),
        ),
    ]
