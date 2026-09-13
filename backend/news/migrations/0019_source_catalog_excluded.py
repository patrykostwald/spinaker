from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0018_source_catalog')]
    operations = [
        migrations.AlterField(model_name='source', name='catalog_stage',
            field=models.CharField('etap katalogowy', max_length=16, default='configured',
                choices=[('candidate', 'Kandydat'), ('configured', 'Skonfigurowane'), ('excluded', 'Wykluczone')],
                help_text='Skonfigurowane nie oznacza zweryfikowanego kanału ani kompletnego archiwum.')),
    ]
