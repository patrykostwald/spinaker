from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('news', '0176_mediamention_lobbying')]
    operations = [
        migrations.AlterField(model_name='publicfiguremediamention', name='organisation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='media_mentions', to='news.registeredorganisation',
                                    help_text='Podmiot z KRS. Puste dla podmiotu bez wpisu w KRS (wtedy nazwa, identyfikator i link do rejestru poniżej).')),
        migrations.AddField(model_name='publicfiguremediamention', name='entity_name',
            field=models.CharField(blank=True, max_length=300, help_text='Nazwa podmiotu bez wpisu w KRS (np. jednoosobowa działalność, fundusz, gmina).')),
        migrations.AddField(model_name='publicfiguremediamention', name='entity_identifier',
            field=models.CharField(blank=True, max_length=40, help_text='Identyfikator podmiotu bez KRS, np. „NIP 1234563218” albo „REGON …”.')),
        migrations.AddField(model_name='publicfiguremediamention', name='entity_register_url',
            field=models.URLField(blank=True, max_length=1024, help_text='Link do właściwego rejestru (CEIDG, BIP, rejestr urzędowy); https.')),
        migrations.AddConstraint(model_name='publicfiguremediamention',
            constraint=models.UniqueConstraint(condition=models.Q(('organisation__isnull', True)), fields=('public_figure', 'entity_name', 'source_url'),
                                               name='unique_media_mention_entity_per_source')),
    ]
