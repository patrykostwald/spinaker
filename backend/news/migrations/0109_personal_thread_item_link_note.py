from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0108_social_manager')]

    operations = [
        migrations.AddField(
            model_name='personalcontextthreaditem',
            name='link_note',
            field=models.CharField(blank=True, default='', max_length=280),
        ),
        migrations.AddConstraint(
            model_name='personalcontextthreaditem',
            constraint=models.CheckConstraint(
                condition=~models.Q(position=0) | models.Q(link_note=''),
                name='personal_thread_first_without_link_note',
            ),
        ),
    ]
