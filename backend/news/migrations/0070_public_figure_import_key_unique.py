from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [('news', '0069_keep_former_cabinet_profiles_public')]

    operations = [
        migrations.AddConstraint(
            model_name='publicfigure',
            constraint=models.UniqueConstraint(
                fields=('import_key',), condition=Q(import_key__gt=''),
                name='news_public_figure_nonempty_import_key_unique',
            ),
        ),
    ]
