from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0135_agents_pracownia_osint'),
    ]

    operations = [
        migrations.AlterField(
            model_name='agentnote',
            name='agent',
            field=models.CharField(choices=[(v, v) for v in ('strateg', 'pielgrzym', 'ekspert', 'recenzent', 'projektant', 'kartograf', 'zwiadowca', 'prawnik', 'dziennikarz', 'kontroler', 'architekt', 'wynalazca')], max_length=12),
        ),
    ]
