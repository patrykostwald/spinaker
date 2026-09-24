from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        # PostgreSQL does not bundle a Polish stemming dictionary. Unicode
        # token matching works with simple; see docs/SEARCH.md for stemming.
        schema_editor.execute("CREATE INDEX IF NOT EXISTS article_title_fts ON news_article USING gin (to_tsvector('simple'::regconfig, COALESCE(title, '')))")


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('DROP INDEX IF EXISTS article_title_fts')


class Migration(migrations.Migration):
    dependencies = [('news', '0002_mvp_fields')]
    operations = [migrations.RunPython(install, uninstall)]
