# Generated manually for the dedicated inbound outreach mailbox.
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('news', '0049_source_daily_fetch_budget')]

    operations = [
        migrations.CreateModel(
            name='SourceContactReply',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_id', models.CharField(max_length=998, unique=True)),
                ('in_reply_to', models.CharField(blank=True, max_length=998)),
                ('sender', models.CharField(max_length=512)),
                ('subject', models.CharField(blank=True, max_length=998)),
                ('received_at', models.DateTimeField(blank=True, null=True)),
                ('received_at_mailbox', models.DateTimeField(default=django.utils.timezone.now)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('contact_card', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inbound_replies', to='news.sourcecontactcard')),
            ],
            options={'ordering': ['-received_at_mailbox', '-pk']},
        ),
    ]
