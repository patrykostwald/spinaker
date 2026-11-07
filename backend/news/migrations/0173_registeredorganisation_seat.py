from django.db import migrations, models


class Migration(migrations.Migration):
    """Siedziba podmiotu z odpisu KRS (6.11.2026): miejscowość, kod pocztowy, województwo; drugi składnik dopasowania po nazwie."""

    dependencies = [('news', '0172_merge_0170_clientnote_file_0171_krs_kolejka')]

    operations = [
        migrations.AddField(model_name='registeredorganisation', name='seat_city',
                            field=models.CharField(blank=True, db_index=True, help_text='Miejscowość siedziby z odpisu KRS (dopasowanie po nazwie i siedzibie).', max_length=128)),
        migrations.AddField(model_name='registeredorganisation', name='seat_postal_code',
                            field=models.CharField(blank=True, help_text='Kod pocztowy siedziby z odpisu KRS (bez ulicy).', max_length=6)),
        migrations.AddField(model_name='registeredorganisation', name='seat_voivodeship',
                            field=models.CharField(blank=True, help_text='Województwo siedziby z odpisu KRS.', max_length=64)),
    ]
