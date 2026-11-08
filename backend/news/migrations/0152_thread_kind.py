from django.db import migrations, models


def fill(apps, schema_editor):
    """Istniejące spinki: rodzaj z pochodzenia (diagnoza, przekaz dnia, sygnały); czytelnicy - kontekst."""
    Thread = apps.get_model('news', 'PersonalContextThread')
    Thread.objects.filter(diagnosis__isnull=False).update(kind='diagnoza')
    Thread.objects.filter(narrative_message__isnull=False).update(kind='przekaz_dnia')
    Thread.objects.filter(signal_kind='lobbying').update(kind='sygnal_lobbingu')
    Thread.objects.filter(signal_kind='new_narrative').update(kind='nowa_narracja')


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0151_nowe_zrodla'),
    ]

    operations = [
        migrations.AddField(
            model_name='personalcontextthread',
            name='kind',
            field=models.CharField(choices=[('diagnoza', 'Diagnoza'), ('przekaz_dnia', 'Przekaz dnia'), ('nowa_narracja', 'Nowa narracja'),
                                            ('sygnal_lobbingu', 'Sygnał lobbingu'), ('kontekst', 'Kontekst'), ('sprzecznosc', 'Sprzeczność'),
                                            ('sprawdzam', 'Sprawdzam'), ('pytanie', 'Pytanie')], default='kontekst', max_length=16),
        ),
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
