# Generated manually for the reviewable public-profile link.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('news', '0063_personal_context_and_comment_reports')]

    operations = [
        migrations.AddField(
            model_name='publicfigure',
            name='parliamentary_roster_entry',
            field=models.ForeignKey(blank=True, help_text='Opcjonalne, ręcznie sprawdzone połączenie z mandatem. Nie jest ustalane po nazwisku.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='public_figure_profiles', to='news.parliamentaryrosterentry'),
        ),
    ]
