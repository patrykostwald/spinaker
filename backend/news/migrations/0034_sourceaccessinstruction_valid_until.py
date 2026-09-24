from django.db import migrations, models
from news.models import access_instruction_default_expiry


class Migration(migrations.Migration):
    dependencies = [('news', '0033_sourceusagedecision')]

    operations = [
        migrations.AddField(
            model_name='sourceaccessinstruction',
            name='valid_until',
            field=models.DateTimeField(blank=True, default=access_instruction_default_expiry, null=True),
        ),
    ]
