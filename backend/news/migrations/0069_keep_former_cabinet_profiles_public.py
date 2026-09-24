from django.db import migrations


def restore_former_cabinet_profiles(apps, schema_editor):
    PublicFigure = apps.get_model('news', 'PublicFigure')
    PublicFigure.objects.filter(import_key__startswith='kprm-cabinet:', status='former', archived=True).update(archived=False)


class Migration(migrations.Migration):
    dependencies = [('news', '0068_public_figure_name_not_unique')]

    operations = [migrations.RunPython(restore_former_cabinet_profiles, migrations.RunPython.noop)]
