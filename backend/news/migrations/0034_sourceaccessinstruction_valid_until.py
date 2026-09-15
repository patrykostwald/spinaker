from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0033_sourceusagedecision')]

    operations = [
        migrations.AddField(
            model_name='sourceaccessinstruction',
            name='valid_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
