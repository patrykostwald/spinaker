import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0052_political_account_candidates')]

    operations = [
        migrations.AlterField(
            model_name='politicalaccount', name='camp',
            field=models.CharField(choices=[('government', 'Obóz rządzący'), ('opposition', 'Opozycja'), ('public', 'Instytucja publiczna')], max_length=12),
        ),
        migrations.AlterField(
            model_name='politicalpost', name='camp_at_collection',
            field=models.CharField(choices=[('government', 'Obóz rządzący'), ('opposition', 'Opozycja'), ('public', 'Instytucja publiczna')], max_length=12),
        ),
        migrations.AlterField(
            model_name='politicalaccountcandidate', name='proposed_camp',
            field=models.CharField(blank=True, choices=[('government', 'Obóz rządzący'), ('opposition', 'Opozycja'), ('public', 'Instytucja publiczna')], help_text='Wymagane przed utworzeniem konta do pobierania.', max_length=12),
        ),
        migrations.RunPython(
            lambda apps, schema_editor: apps.get_model('news', 'PoliticalAccountCandidate').objects.filter(classification='public', proposed_camp='').update(proposed_camp='public'),
            migrations.RunPython.noop,
        ),
    ]
