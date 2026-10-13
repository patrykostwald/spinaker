from django.db import migrations


COLOR_MAP = {
    'lilac': 'lila', 'plum': 'wrzos', 'rose': 'fuksja', 'coral': 'roz',
    'amber': 'brzoskwinia', 'sand': 'piasek', 'olive': 'cytryna', 'moss': 'pistacja',
    'ash': 'piasek', 'slate': 'lila', 'teal': 'pistacja',
}


def map_colors(apps, schema_editor):
    Profile = apps.get_model('spina3', 'Spina3Profile')
    for old, new in COLOR_MAP.items():
        Profile.objects.using(schema_editor.connection.alias).filter(nick_color=old).update(nick_color=new)


class Migration(migrations.Migration):
    dependencies = [('spina3', '0003_contract_20261014')]
    # Mapowanie stratne: cofnięcie nie odtwarza starych kolorów.
    operations = [migrations.RunPython(map_colors, migrations.RunPython.noop)]
