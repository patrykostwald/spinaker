from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0017_archivejob_priority')]
    operations = [
        migrations.AlterField(model_name='source', name='url',
            field=models.URLField('adres URL', unique=True, max_length=4096, blank=True, null=True)),
        migrations.AddField(model_name='source', name='catalog_notes',
            field=models.TextField('notatki katalogowe', blank=True)),
        migrations.AddField(model_name='source', name='catalog_stage',
            field=models.CharField('etap katalogowy', max_length=16, default='configured',
                choices=[('candidate', 'Kandydat'), ('configured', 'Skonfigurowane')],
                help_text='Skonfigurowane nie oznacza zweryfikowanego kanału ani kompletnego archiwum.')),
    ]
