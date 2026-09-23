from io import StringIO

import pytest
from django.core.management import call_command

from news.models import ImportState, Source, SourceReviewDecision, SourceType
from scraper.source_terms_discovery import classify_terms_page


def test_classification_proposes_card_only_with_clear_permission_and_channel():
    result = classify_terms_page(b'<p>Informacje mozna ponownie wykorzystywac na CC BY.</p>', True)
    assert result['status'] == 'proposed_metadata_card_requires_editorial_approval'


def test_classification_keeps_source_inactive_when_terms_require_consent():
    result = classify_terms_page(b'<p>Wykorzystanie wymaga uprzedniej zgody.</p>', True)
    assert result['status'] == 'clear_denial_keep_inactive'


@pytest.mark.django_db
def test_command_writes_a_proposal_without_changing_source_state(tmp_path, monkeypatch):
    source = Source.objects.create(name='Office', url='https://office.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    SourceReviewDecision.objects.create(source=source, decision='contact_required', reason='Terms found.', reviewed_by='test')
    ImportState.objects.create(name=f'source-check:{source.pk}', cursor={
        'rss': {'status': 'working', 'url': 'https://office.example/feed'},
        'legal_terms_discovery': {'terms_pages': [{'url': 'https://office.example/terms', 'status': 'ok'}]},
    })
    monkeypatch.setattr('scraper.management.commands.classify_source_reuse_terms.worker',
        lambda source, cursor, network: (source.pk, {'version': 1, 'status': 'proposed_metadata_card_requires_editorial_approval', 'pages': [], 'checked_at': '2026-09-23T00:00:00+00:00', 'signature': 'test'}))
    call_command('classify_source_reuse_terms', '--apply', '--output', str(tmp_path / 'classification.md'), stdout=StringIO())
    source.refresh_from_db()
    state = ImportState.objects.get(name=f'source-check:{source.pk}')
    assert state.cursor['legal_terms_classification']['status'] == 'proposed_metadata_card_requires_editorial_approval'
    assert not source.is_active and source.catalog_stage == 'candidate'
