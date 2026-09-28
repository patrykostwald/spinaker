from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0085_weekly_report'),
    ]

    operations = [
        migrations.AddField(
            model_name='politicalpost',
            name='archive_url',
            field=models.URLField(blank=True, default='', max_length=500,
                                  help_text='Kopia usuniętego wpisu w publicznym archiwum (Wayback Machine) — tylko link, treści nie przechowujemy.'),
        ),
        migrations.AddField(
            model_name='politicalpost',
            name='archive_checked_at',
            field=models.DateTimeField(blank=True, null=True, help_text='Ostatnie szukanie kopii usuniętego wpisu w archiwum.'),
        ),
    ]
