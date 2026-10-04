from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0138_agents_automatyk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='agentnote',
            name='agent',
            field=models.CharField(choices=[(v, v) for v in ('strateg', 'pielgrzym', 'ekspert', 'recenzent', 'projektant', 'kartograf', 'zwiadowca', 'prawnik', 'dziennikarz', 'kontroler', 'architekt', 'wynalazca', 'technolog', 'automatyk', 'opiekun')], max_length=12),
        ),
    ]
