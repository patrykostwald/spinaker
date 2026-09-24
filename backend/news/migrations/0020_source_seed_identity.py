from hashlib import sha256
from django.db import migrations, models


def preserve_existing_identity(apps, schema_editor):
    Source = apps.get_model('news', 'Source')
    alias = schema_editor.connection.alias
    for source in Source.objects.using(alias).exclude(url__isnull=True).exclude(url='').only('pk', 'url').iterator():
        Source.objects.using(alias).filter(pk=source.pk).update(
            catalog_seed_key=sha256(source.url.encode('utf-8')).hexdigest())


class Migration(migrations.Migration):
    dependencies = [('news', '0019_source_catalog_excluded')]
    operations = [
        migrations.AddField(model_name='source', name='catalog_seed_key',
            field=models.CharField(max_length=64, unique=True, blank=True, null=True, editable=False)),
        migrations.RunPython(preserve_existing_identity, migrations.RunPython.noop),
    ]
