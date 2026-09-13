from django.db import migrations

def classify(apps, schema_editor):
    Article = apps.get_model('news', 'Article')
    Article.objects.filter(ingestion_method='rss', category='other', category_reviewed=False, source__source_type__in=['portal', 'newspaper', 'rss']).update(category='article')

class Migration(migrations.Migration):
    dependencies = [('news', '0010_threaditem_external_url_alter_threaditem_article')]
    operations = [migrations.RunPython(classify, migrations.RunPython.noop)]
