# Generated manually to keep the access-card schema change reviewable.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0047_align_fetchattempt_request_id_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='sourceaccessinstruction',
            name='allowed_path_patterns',
            field=models.JSONField(blank=True, default=list,
                help_text='Opcjonalne ścisłe wzorce ścieżek, np. /sejm/term10/votings/{int}.'),
        ),
    ]
