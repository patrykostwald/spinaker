from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0050_sourcecontactreply')]

    operations = [
        migrations.AddField(
            model_name='sourcecontactcard', name='contact_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='sourcecontactcard', name='contact_evidence_url',
            field=models.URLField(blank=True, max_length=1024),
        ),
        migrations.AddField(
            model_name='sourcecontactcard', name='contact_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
