from io import StringIO

import pytest
from django.core.management import call_command

from news.models import ImportState, Source, SourceReviewDecision, SourceType
from scraper.source_terms_discovery import inspect_source_terms
from scraper.management.commands.discover_source_reuse_terms import worker
from scraper.source_contact_queue import contact_candidates


class FakeNetwork:
    def __init__(self, pages):
        self.pages = pages

    def fetch(self, url):
        return self.pages[url], url, []


@pytest.mark.django_db
def test_discovery_finds_official_reuse_terms_link():
    source = Source.objects.create(name='Office', url='https://office.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    result = inspect_source_terms(source, FakeNetwork({
        'https://office.example': b'<a href="/ponowne-wykorzystanie">Ponowne wykorzystywanie</a>',
        'https://office.example/ponowne-wykorzystanie': b'<p>Informacje mozna ponownie wykorzystywac. CC BY.</p>',
    }))
    assert result['status'] == 'possible_reuse_basis_requires_editorial_review'
    assert result['terms_pages'][0]['positive_markers']


@pytest.mark.django_db
def test_discovery_keeps_an_explicit_cross_host_bip_terms_link():
    source = Source.objects.create(name='Office', url='https://office.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    result = inspect_source_terms(source, FakeNetwork({
        'https://office.example': b'<a href="https://bip.office.example/ponowne-wykorzystanie">Warunki ponownego wykorzystania</a>',
        'https://bip.office.example/ponowne-wykorzystanie': b'<p>Informacje mozna ponownie wykorzystywac.</p>',
    }))
    assert result['terms_pages'][0]['url'] == 'https://bip.office.example/ponowne-wykorzystanie'


@pytest.mark.django_db
def test_command_saves_evidence_without_changing_source_state(tmp_path, monkeypatch):
    source = Source.objects.create(name='Office', url='https://office.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    SourceReviewDecision.objects.create(source=source, decision='contact_required', reason='No terms.', reviewed_by='test')
    monkeypatch.setattr('scraper.management.commands.discover_source_reuse_terms.inspect_source_terms',
        lambda source, network: {'version': 1, 'source_url': source.url, 'status': 'terms_link_found', 'homepage': source.url, 'terms_pages': [], 'error': ''})
    output = tmp_path / 'discovery.md'
    call_command('discover_source_reuse_terms', '--apply', '--output', str(output), stdout=StringIO())
    state = ImportState.objects.get(name=f'source-check:{source.pk}')
    source.refresh_from_db()
    assert state.cursor['legal_terms_discovery']['status'] == 'terms_link_found'
    assert not source.is_active and source.catalog_stage == 'candidate'


@pytest.mark.django_db
def test_command_includes_contact_queue_source_without_explicit_contact_decision(tmp_path, monkeypatch):
    source = Source.objects.create(name='Publisher', url='https://publisher.example', source_type=SourceType.PORTAL,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    monkeypatch.setattr('scraper.management.commands.discover_source_reuse_terms.inspect_source_terms',
        lambda source, network: {'version': 1, 'source_url': source.url, 'status': 'terms_link_found', 'homepage': source.url, 'terms_pages': [], 'error': ''})
    call_command('discover_source_reuse_terms', '--apply', '--output', str(tmp_path / 'discovery.md'), stdout=StringIO())
    assert ImportState.objects.get(name=f'source-check:{source.pk}').cursor['legal_terms_discovery']['status'] == 'terms_link_found'


@pytest.mark.django_db
def test_terms_discovery_and_contact_register_share_exact_source_list(tmp_path, monkeypatch):
    Source.objects.create(name='Publisher', url='https://publisher.example', source_type=SourceType.PORTAL,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    monkeypatch.setattr('scraper.management.commands.discover_source_reuse_terms.inspect_source_terms',
        lambda source, network: {'version': 1, 'source_url': source.url, 'status': 'terms_link_found', 'homepage': source.url, 'terms_pages': [], 'error': ''})
    call_command('discover_source_reuse_terms', '--apply', '--output', str(tmp_path / 'discovery.md'), stdout=StringIO())
    call_command('source_contact_register', '--output', str(tmp_path / 'contacts.md'), stdout=StringIO())
    sources, _ = contact_candidates()
    assert f'Contact candidates: **{len(sources)}**.' in (tmp_path / 'discovery.md').read_text(encoding='utf-8')
    assert f'Sources requiring later confirmation: **{len(sources)}**.' in (tmp_path / 'contacts.md').read_text(encoding='utf-8')


@pytest.mark.django_db
def test_worker_records_unexpected_source_error(monkeypatch):
    source = Source.objects.create(name='Office', url='https://office.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    monkeypatch.setattr('scraper.management.commands.discover_source_reuse_terms.inspect_source_terms',
        lambda source, network: (_ for _ in ()).throw(RuntimeError('bad page')))
    source_id, result = worker(source, object())
    assert source_id == source.pk
    assert result['status'] == 'unavailable'
    assert result['error'] == 'RuntimeError'
