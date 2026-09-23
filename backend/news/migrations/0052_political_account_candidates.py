# Generated manually for the staff-only account candidate workflow.
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0051_sourcecontactcard_verified_email')]

    operations = [
        migrations.CreateModel(
            name='PoliticalAccountCandidate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('handle', models.CharField(max_length=15, unique=True, validators=[django.core.validators.RegexValidator('^[A-Za-z0-9_]{1,15}$', 'Podaj nazwę konta X bez @.')])),
                ('display_name', models.CharField(max_length=150)),
                ('classification', models.CharField(choices=[('government', 'Obóz rządzący'), ('opposition', 'Opozycja'), ('public', 'Instytucja publiczna'), ('independent', 'Niezależne / do oceny')], max_length=12)),
                ('proposed_camp', models.CharField(blank=True, choices=[('government', 'Obóz rządzący'), ('opposition', 'Opozycja')], help_text='Wymagane przed utworzeniem konta do pobierania.', max_length=12)),
                ('confirmation_url', models.URLField(blank=True, max_length=1024)),
                ('confirmation_note', models.TextField(blank=True)),
                ('resolution_error', models.CharField(blank=True, editable=False, max_length=240)),
                ('resolved_at', models.DateTimeField(blank=True, editable=False, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('resolved_account', models.OneToOneField(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='candidate', to='news.politicalaccount')),
            ],
            options={'ordering': ['classification', 'handle']},
        ),
        migrations.RunPython(
            lambda apps, schema_editor: apps.get_model('news', 'PoliticalAccountCandidate').objects.bulk_create([
                apps.get_model('news', 'PoliticalAccountCandidate')(handle='donaldtusk', display_name='Donald Tusk', classification='government', proposed_camp='government', confirmation_url='https://www.gov.pl/web/primeminister/pmmm222'),
                apps.get_model('news', 'PoliticalAccountCandidate')(handle='KONFEDERACJA_', display_name='Konfederacja', classification='opposition', proposed_camp='opposition', confirmation_url='https://konfederacja.pl/oficjalnie-wlaczamy-sie-w-zbiorke-podpisow-za-odwolaniem-miszalskiego/'),
                apps.get_model('news', 'PoliticalAccountCandidate')(handle='EwaZajaczkowska', display_name='Ewa Zajączkowska-Hernik', classification='opposition', proposed_camp='opposition', confirmation_url='https://konfederacja.pl/ewa-zajaczkowska-hernik-rzecznikiem-prasowym-konfederacji/?amp=1'),
                apps.get_model('news', 'PoliticalAccountCandidate')(handle='TomaszSiemoniak', display_name='Tomasz Siemoniak', classification='government', proposed_camp='government', confirmation_url='https://www.abw.gov.pl/ftp/foto/Wydawnictwo/terroryzm/nr8/T-SAP_-_8_-_CALOSC_-_8.pdf'),
                *[apps.get_model('news', 'PoliticalAccountCandidate')(handle=handle, display_name=name, classification='public') for handle, name in [('KancelariaSejmu','Kancelaria Sejmu'),('PolskiSenat','Senat'),('MSZ_RP','MSZ'),('MON_GOV_PL','MON'),('MSWiA_GOV_PL','MSWiA'),('RCB_RP','RCB'),('MZ_GOV_PL','MZ'),('MRiRW_GOV_PL','MRiRW'),('ME_GOV_PL','ME')]],
            ], ignore_conflicts=True),
            migrations.RunPython.noop,
        ),
    ]
