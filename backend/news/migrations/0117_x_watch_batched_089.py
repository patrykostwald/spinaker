from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0116_followed_posts_088')]

    operations = [
        migrations.AddField(model_name='politicalaccount', name='last_profile_read_at',
            field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='politicalpost', name='watch_priority',
            field=models.BooleanField(default=False, editable=False)),
        migrations.AddField(model_name='politicalread', name='account_ids',
            field=models.JSONField(default=list, editable=False)),
        migrations.AddField(model_name='politicalread', name='response_body',
            field=models.BinaryField(null=True, editable=False)),
    ]
