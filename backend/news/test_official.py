from copy import deepcopy
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from news.models import Article, Ballot, EvidenceLink, OfficialRecord, SourceAccessInstruction
from news.metadata import extract_metadata
from scraper.official import save_voting, save_document


def approve_api(provider):
    from django.utils import timezone
    from scraper.official import API, official_source
    source = official_source(provider)
    endpoint = API + ('/eli' if provider == 'eli' else '/sejm')
    return SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='api',
        allowed_scope='metadata', endpoint=endpoint,
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test',
        minimum_interval_seconds=3, daily_request_cap=24)

# Synthetic records are test-only and never loaded into the portal database.
@pytest.fixture
def voting_payload():
    return {'term': 10, 'sitting': 1, 'votingNumber': 2, 'title': 'Testowy projekt o rynku kryptoaktywów',
        'description': 'wniosek o ponowne uchwalenie ustawy', 'date': '2025-12-05T15:01:14',
        'kind': 'ELECTRONIC', 'yes': 1, 'no': 1, 'votes': [
            {'MP': 1, 'firstName': 'Jan', 'lastName': 'Testowy', 'club': 'T', 'vote': 'NO'},
            {'MP': 2, 'firstName': 'Anna', 'lastName': 'Przykładowa', 'club': 'P', 'vote': 'YES'}]}


@pytest.mark.django_db
def test_official_atomic_idempotent_and_motion(voting_payload):
    assert save_voting(voting_payload, 10, 1, 2)
    assert not save_voting(voting_payload, 10, 1, 2)
    assert Article.objects.count() == 1 and Ballot.objects.count() == 2
    assert Article.objects.get().voting.motion == voting_payload['description']
    assert OfficialRecord.objects.get().raw_data == voting_payload
    correction = deepcopy(voting_payload)
    correction['votes'][0]['club'] = 'Nowy klub'
    save_voting(correction, 10, 1, 2)
    assert OfficialRecord.objects.get().revisions.get().raw_data == voting_payload
    assert OfficialRecord.objects.get().raw_data == correction
    broken = deepcopy(voting_payload)
    broken['votes'][0]['vote'] = 'UNKNOWN'
    with pytest.raises(ValueError):
        save_voting(broken, 10, 1, 2)
    assert Ballot.objects.get(mp_id=1).vote == 'NO'
    assert OfficialRecord.objects.get().raw_data == correction


@pytest.mark.django_db
def test_search_member_topic_and_evidence(voting_payload):
    cache.clear()
    save_voting(voting_payload, 10, 1, 2)
    client = APIClient()
    result = client.get('/api/search/', {'q': 'krypto Testowy'}).json()
    assert result['total'] == 1
    row = next(iter(result['timeline'].values()))[0]
    assert row['voting']['matching_ballots'][0]['vote'] == 'NO'
    assert client.get('/api/search/', {'q': 'firma Testowy'}).json()['total'] == 0
    EvidenceLink.objects.create(article=Article.objects.get(), phrase='firma', source_url='https://example.org/evidence', explanation='Test-only evidence')
    cache.clear()
    assert client.get('/api/search/', {'q': 'firma Testowy'}).json()['total'] == 1
    ballots = client.get(f"/api/articles/{row['id']}/ballots/", {'q': 'Testowy'}).json()
    assert ballots['count'] == 1 and ballots['results'][0]['vote'] == 'NO'


@pytest.mark.django_db
def test_day_precision_and_original_long_title():
    data = {'title': 'A' * 600, 'promulgation': '2026-09-04'}
    save_document(data, 'eli', 'DU/2026/1', 'https://api.sejm.gov.pl/eli/acts/DU/2026/1',
        'https://eli.gov.pl/eli/DU/2026/1/ogl', 'legislation', 'promulgation')
    a = Article.objects.get()
    assert a.date_precision == 'day' and len(a.title) == 500
    assert a.description == data['title'] and a.official_record.raw_data == data


def test_url_metadata_does_not_invent_author_or_timezone():
    data = extract_metadata(b'<title>Publisher title</title><meta property="article:published_time" content="2026-01-02T10:00:00">', 'https://example.org/a')
    assert data['title'] == 'Publisher title'
    assert data['author'] == '' and data['published_date'] is None


@pytest.mark.django_db
def test_url_preview_requires_staff():
    assert APIClient().post('/api/editor/preview-url/', {'url': 'https://example.org'}).status_code == 403
    assert APIClient().get('/api/editor/status/').status_code == 403


@pytest.mark.django_db
def test_eli_changes_reads_all_pages():
    from unittest.mock import patch
    from scraper.official import import_eli_changes
    approve_api('eli')
    rows = [{'publisher': 'DU', 'year': 2026, 'pos': position, 'title': f'Test {position}', 'promulgation': '2026-01-01'} for position in (1, 2)]
    with patch('scraper.official.fetch_json', side_effect=[{'items': [rows[0]], 'totalCount': 2}, {'items': [rows[1]], 'totalCount': 2}]) as fetch:
        assert import_eli_changes('2026-01-01T00:00:00') == 2
        assert fetch.call_args.kwargs['offset'] == 1


@pytest.mark.django_db
def test_failed_official_task_does_not_advance_last_success():
    from unittest.mock import patch
    from django.utils import timezone
    from news.models import ImportState
    from scraper.tasks import import_official_task
    cache.clear()
    stamp = timezone.now()
    state = ImportState.objects.create(name='official:eli', last_success=stamp)
    with patch('scraper.official.official_access_allowed', return_value=True), \
            patch('scraper.official.import_eli_changes', side_effect=TimeoutError):
        with pytest.raises(TimeoutError):
            import_official_task('eli')
    state.refresh_from_db()
    assert state.last_success == stamp and state.last_error == 'TimeoutError'
