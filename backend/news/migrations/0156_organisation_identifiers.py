# Drzewo przepływu pieniędzy (właściciel 6.10): NIP i REGON podmiotu z odpisu KRS do łączenia zamówień i dotacji po identyfikatorach.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0155_clinic_message_error'),
    ]

    operations = [
        migrations.AddField(
            model_name='registeredorganisation',
            name='nip',
            field=models.CharField(blank=True, db_index=True, help_text='NIP z odpisu KRS (same cyfry).', max_length=10),
        ),
        migrations.AddField(
            model_name='registeredorganisation',
            name='regon',
            field=models.CharField(blank=True, db_index=True, help_text='REGON z odpisu KRS (same cyfry).', max_length=14),
        ),
    ]
