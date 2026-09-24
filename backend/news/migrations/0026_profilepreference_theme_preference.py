from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('news', '0025_journalist_threads_sponsorship'),
    ]

    operations = [
        migrations.AddField(
            model_name='profilepreference',
            name='theme_preference',
            field=models.CharField(
                choices=[
                    ('auto', 'Automatyczny'),
                    ('dark', 'Ciemny'),
                    ('light', 'Jasny'),
                    ('pastel', 'Pastelowy'),
                ],
                default='auto',
                max_length=8,
            ),
        ),
    ]
