from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0139_agents_opiekun'),
    ]

    operations = [
        migrations.AlterField(
            model_name='agentnote',
            name='agent',
            field=models.CharField(choices=[(v, v) for v in ('strateg', 'pielgrzym', 'ekspert', 'recenzent', 'projektant', 'kartograf', 'zwiadowca', 'prawnik', 'dziennikarz', 'kontroler', 'architekt', 'wynalazca', 'technolog', 'automatyk', 'opiekun', 'dyrygent')], max_length=12),
        ),
    ]
