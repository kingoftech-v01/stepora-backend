from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dreams', '0014_add_is_public_to_dream'),
    ]

    operations = [
        migrations.AddField(
            model_name='dream',
            name='is_favorited',
            field=models.BooleanField(
                default=False,
                help_text='Whether the user has favorited this dream on the vision board',
            ),
        ),
    ]
