from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0067_parliamentary_roster_term')]

    operations = [
        migrations.AlterField(
            model_name='publicfigure',
            name='canonical_name',
            field=models.CharField(help_text='Nazwa wyświetlana; nie stanowi samodzielnego identyfikatora osoby.', max_length=255),
        ),
    ]
