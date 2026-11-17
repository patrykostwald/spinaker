from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0136_agents_wynalazca'),
    ]

    operations = [
        migrations.AlterField(
            model_name='agentnote',
            name='agent',
            field=models.CharField(choices=[(v, v) for v in ('strateg', 'pielgrzym', 'ekspert', 'recenzent', 'projektant', 'kartograf', 'zwiadowca', 'prawnik', 'dziennikarz', 'kontroler', 'architekt', 'wynalazca', 'technolog')], max_length=12),
        ),
    ]
