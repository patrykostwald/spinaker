# Przekaz dnia: zapisany powód niepowodzenia (wiersz status='failed'), żeby błąd nie ginął w logu (6.10).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0154_sprint_issues'),
    ]

    operations = [
        migrations.AddField(
            model_name='clinicdailymessage',
            name='error',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
    ]
