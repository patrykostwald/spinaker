# Zwiadowca rozwiązań (7.10.2026): nowy agent w dzienniku propozycji.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0152_thread_kind'),
    ]

    operations = [
        migrations.AlterField(
            model_name='agentnote',
            name='agent',
            field=models.CharField(choices=[('strateg', 'strateg'), ('pielgrzym', 'pielgrzym'), ('ekspert', 'ekspert'), ('recenzent', 'recenzent'), ('projektant', 'projektant'), ('kartograf', 'kartograf'), ('zwiadowca', 'zwiadowca'), ('prawnik', 'prawnik'), ('dziennikarz', 'dziennikarz'), ('kontroler', 'kontroler'), ('architekt', 'architekt'), ('wynalazca', 'wynalazca'), ('technolog', 'technolog'), ('automatyk', 'automatyk'), ('opiekun', 'opiekun'), ('dyrygent', 'dyrygent'), ('zamowienia', 'zamowienia'), ('rozwiazania', 'rozwiazania')], max_length=12),
        ),
    ]
