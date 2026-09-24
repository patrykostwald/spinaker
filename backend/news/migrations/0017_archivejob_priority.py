from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0016_airesearchcall')]
    operations = [migrations.AddField(model_name='archivejob', name='priority',
        field=models.PositiveSmallIntegerField(default=0, db_index=True))]
