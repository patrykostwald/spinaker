# Generated manually for the reviewed public-figure/material context graph.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('news', '0072_publicfigurerole'),
    ]

    operations = [
        migrations.CreateModel(
            name='PublicFigureArticleReference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference_kind', models.CharField(choices=[('subject', 'Materiał dotyczy osoby'), ('speaker', 'Wypowiedź osoby'), ('interviewee', 'Osoba udziela wywiadu'), ('mentioned', 'Osoba jest wymieniona')], max_length=16)),
                ('evidence_note', models.TextField(blank=True)),
                ('verification_status', models.CharField(choices=[('pending_review', 'Do przeglądu'), ('confirmed', 'Potwierdzone przez redakcję'), ('rejected', 'Odrzucone')], db_index=True, default='pending_review', max_length=20)),
                ('verified_at', models.DateTimeField(blank=True, editable=False, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='public_figure_references', to='news.article')),
                ('public_figure', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='article_references', to='news.publicfigure')),
                ('verified_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='verified_public_figure_article_references', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-article__published_date', '-pk']},
        ),
        migrations.AddConstraint(
            model_name='publicfigurearticlereference',
            constraint=models.UniqueConstraint(fields=('public_figure', 'article', 'reference_kind'), name='unique_public_figure_article_reference_kind'),
        ),
    ]
