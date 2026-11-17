from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0110_interview_votes')]
    operations = [
        migrations.AddField(model_name='clinicdailymessage', name='stats', field=models.JSONField(default=dict, blank=True)),
        migrations.AddField(model_name='clinicdailymessage', name='thesis', field=models.CharField(max_length=160, blank=True)),
        migrations.AddField(model_name='clinicdailymessage', name='points', field=models.JSONField(default=list, blank=True)),
        migrations.AddField(model_name='clinicdailymessage', name='tone', field=models.JSONField(default=list, blank=True)),
    ]
