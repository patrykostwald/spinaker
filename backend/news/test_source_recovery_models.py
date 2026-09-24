import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from news.models import ArchiveJob, Source, SourceAccessInstruction, SourceContactCard, SourceRecoveryCase


@pytest.mark.django_db
def test_recovery_case_cannot_mark_repaired_without_approved_instruction_and_positive_dry_run():
    source = Source.objects.create(name='Recovery', url='https://recovery.example')
    case = SourceRecoveryCase(source=source, trigger='terminal_error',
        failure_fingerprint='network', status='repaired')
    with pytest.raises(ValidationError):
        case.full_clean()


@pytest.mark.django_db
def test_recovery_case_allows_repaired_only_with_reviewed_instruction_and_new_box():
    source = Source.objects.create(name='Recovered', url='https://recovered.example')
    instruction = SourceAccessInstruction.objects.create(source=source, version=1,
        status='approved', channel='sitemap', allowed_scope='metadata',
        endpoint='https://recovered.example/sitemap.xml', terms_url='https://recovered.example/terms',
        evidence={'terms': 'checked'}, reviewed_at=timezone.now(), reviewed_by='editor')
    case = SourceRecoveryCase(source=source, trigger='terminal_error', failure_fingerprint='network',
        status='repaired', proposed_instruction=instruction, boxes_before=10, boxes_after=11,
        dry_run_result={'succeeded': True}, audit_evidence={'terms': 'checked'})
    case.full_clean()


@pytest.mark.django_db
def test_contact_card_needs_human_approval_before_send_status():
    source = Source.objects.create(name='Contact', url='https://contact.example')
    card = SourceContactCard(source=source, status='approved_to_send')
    with pytest.raises(ValidationError):
        card.full_clean()


@pytest.mark.django_db
def test_contact_card_requires_verified_email_before_send_status():
    source = Source.objects.create(name='Verified contact', url='https://verified-contact.example')
    card = SourceContactCard(
        source=source, status='approved_to_send', approval_by='Patryk', approval_at=timezone.now(),
        requested_scope=['metadata'], requested_channels=['rss'], technical_findings={'verified': True},
    )
    with pytest.raises(ValidationError):
        card.full_clean()
    card.contact_email = 'redakcja@example.org'
    card.contact_evidence_url = 'https://example.org/kontakt'
    card.contact_verified_at = timezone.now()
    card.full_clean()


@pytest.mark.django_db
def test_repeated_source_failure_creates_one_open_recovery_case():
    from scraper.archive import _record_recovery_case
    source = Source.objects.create(name='Broken', url='https://broken.example')
    job = ArchiveJob.objects.create(source=source, url='https://broken.example/map.xml', kind='sitemap')
    first = _record_recovery_case(job, 'NewConnectionError', terminal=False)
    second = _record_recovery_case(job, 'NewConnectionError', terminal=False)
    assert first.pk == second.pk
    assert SourceRecoveryCase.objects.filter(source=source).count() == 1
    assert first.trigger == 'retry_threshold'
