from django.db import migrations, models


def set_known_current_terms(apps, schema_editor):
    Roster = apps.get_model('news', 'ParliamentaryRosterEntry')
    Roster.objects.filter(source='sejm', term__isnull=True).update(term=10)
    Roster.objects.filter(source='senat', term__isnull=True).update(term=11)


class Migration(migrations.Migration):
    dependencies = [('news', '0066_sourcethumbnailpolicy')]

    operations = [
        migrations.AddField(
            model_name='parliamentaryrosterentry',
            name='term',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Kadencja wskazana przez oficjalny roster. Wymagana dla mandatów Sejmu.', null=True),
        ),
        migrations.RunPython(set_known_current_terms, migrations.RunPython.noop),
    ]
