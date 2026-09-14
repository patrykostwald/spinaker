from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('news', '0031_sourceaccessinstruction')]
    operations = [
        migrations.CreateModel(
            name='SourceRecoveryCase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('detected', 'Wykryto'), ('triage', 'Triage'), ('cooldown', 'Przerwa techniczna'), ('auditing', 'Audyt'), ('dry_run', 'Mały test'), ('repaired', 'Naprawiono'), ('manual_review', 'Kontrola ręczna'), ('contact_required', 'Wymaga kontaktu'), ('retired', 'Wycofano'), ('closed', 'Zamknięto')], default='detected', max_length=20)),
                ('trigger', models.CharField(choices=[('no_new_boxes', 'Brak nowych boxów'), ('terminal_error', 'Błąd trwały'), ('retry_threshold', 'Próg ponowień'), ('quality_drift', 'Dryf jakości'), ('manual', 'Ręcznie')], max_length=32)),
                ('failure_fingerprint', models.CharField(max_length=128)), ('sample_error', models.CharField(blank=True, max_length=500)),
                ('opened_at', models.DateTimeField(default=django.utils.timezone.now)), ('last_observed_at', models.DateTimeField(default=django.utils.timezone.now)), ('closed_at', models.DateTimeField(blank=True, null=True)), ('last_success_at', models.DateTimeField(blank=True, null=True)),
                ('boxes_before', models.PositiveIntegerField(default=0)), ('boxes_after', models.PositiveIntegerField(default=0)), ('attempt_count', models.PositiveSmallIntegerField(default=0)), ('audit_evidence', models.JSONField(default=dict)), ('dry_run_result', models.JSONField(default=dict)), ('decision_reason', models.TextField(blank=True)), ('decided_by', models.CharField(blank=True, max_length=120)), ('decided_at', models.DateTimeField(blank=True, null=True)),
                ('failed_instruction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='failed_recovery_cases', to='news.sourceaccessinstruction')), ('proposed_instruction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='proposed_recovery_cases', to='news.sourceaccessinstruction')), ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recovery_cases', to='news.source')),
            ], options={'ordering': ['-last_observed_at', '-pk']},
        ),
        migrations.CreateModel(
            name='SourceContactCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('status', models.CharField(choices=[('draft', 'Szkic'), ('ready_for_review', 'Gotowa do kontroli'), ('approved_to_send', 'Zatwierdzona do wysyłki'), ('sent', 'Wysłano ręcznie'), ('answered', 'Odpowiedziano'), ('declined', 'Odmowa'), ('agreement_recorded', 'Zgoda zapisana'), ('closed', 'Zamknięto')], default='draft', max_length=24)), ('publisher_name', models.CharField(blank=True, max_length=255)), ('contact_url', models.URLField(blank=True, max_length=1024)), ('requested_scope', models.JSONField(default=list)), ('requested_channels', models.JSONField(default=list)), ('technical_findings', models.JSONField(default=dict)), ('reason_for_contact', models.TextField(blank=True)), ('message_draft', models.TextField(blank=True)), ('approval_by', models.CharField(blank=True, max_length=120)), ('approval_at', models.DateTimeField(blank=True, null=True)), ('sent_at', models.DateTimeField(blank=True, null=True)), ('delivery_reference', models.CharField(blank=True, max_length=255)), ('reply_summary', models.TextField(blank=True)), ('reply_evidence_url', models.URLField(blank=True, max_length=1024)), ('next_review_at', models.DateTimeField(blank=True, null=True)), ('created_at', models.DateTimeField(auto_now_add=True)),
                ('granted_instruction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='granted_contact_cards', to='news.sourceaccessinstruction')), ('recovery_case', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contact_card', to='news.sourcerecoverycase')), ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contact_cards', to='news.source')),
            ], options={'ordering': ['status', 'next_review_at', 'pk']},
        ),
    ]
