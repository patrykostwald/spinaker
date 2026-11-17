from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0106_poll_vote')]
    operations = [migrations.AddField(
        model_name='spindiagnosis', name='plain',
        field=models.JSONField(blank=True, default=dict, help_text='Prosty pierwszy ekran: title, gist, top.'),
    )]
