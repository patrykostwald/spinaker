from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0081_clinic_interview'),
    ]

    operations = [
        migrations.AddField(
            model_name='spindiagnosis',
            name='x_thread',
            field=models.JSONField(blank=True, default=list, help_text='Synteza diagnozy do wątku na X (darmowy model): wpis otwierający i 2–3 kolejne.'),
        ),
    ]
