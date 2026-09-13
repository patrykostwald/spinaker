from datetime import datetime, timezone as dt_timezone
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from news.models import Article, Source, Thread, EvidenceLink

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 9, 9, 0, 30, tzinfo=dt_timezone.utc)


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    cache.clear()
    monkeypatch.setattr('news.portal.timezone.now', lambda: NOW)


@pytest.fixture
def source():
    return Source.objects.create(name='Onet Wiadomości', url='https://example.org', is_active=True)


def record(source, suffix, date=None, **kwargs):
    return Article.objects.create(source=source, url='https://example.org/' + suffix,
        title=kwargs.pop('title', suffix), published_date=date, **kwargs)


def ids(payload):
    return {row['id'] for row in payload['results']}


def test_top_today_warsaw_not_utc_only_and_no_import_date(source):
    # Warsaw midnight is 22:00 UTC on the previous calendar date.
    today = record(source, 'today', datetime(2026, 9, 8, 22, 1, tzinfo=dt_timezone.utc))
    record(source, 'yesterday', datetime(2026, 9, 8, 21, 59, tzinfo=dt_timezone.utc), discovered_at=NOW)
    record(source, 'unknown', discovered_at=NOW)
    record(source, 'future', datetime(2026, 9, 9, 1, 0, tzinfo=dt_timezone.utc))
    other = Source.objects.create(name='Other publisher', url='https://other.example', is_active=True)
    record(other, 'outside-selection', NOW)
    result = APIClient().get('/api/feed/?mode=top').data
    assert ids(result) == {today.pk} and result['total'] == 1


def test_latest_visibility_null_dates_and_filters(source):
    current = record(source, 'current', NOW, category='interview', tags=['Energia'])
    unknown = record(source, 'unknown', discovered_at=NOW)
    hidden = Source.objects.create(name='Hidden', url='https://hidden.example', is_active=False)
    excluded = Source.objects.create(name='Excluded', url='https://excluded.example', is_active=True, catalog_stage='excluded')
    record(hidden, 'hidden', NOW)
    record(excluded, 'excluded', NOW)
    record(source, 'tweet', NOW, category='tweet')
    client = APIClient()
    latest = client.get('/api/feed/').data
    assert ids(latest) == {current.pk, unknown.pk}
    assert latest['results'][-1]['published_date'] is None
    result = client.get(f'/api/feed/?q=Energia&categories=interview&sources={source.pk}').data
    assert ids(result) == {current.pk}
    assert client.get('/api/feed/?categories=unknown').status_code == 400
    assert client.get('/api/feed/?sources=bad').status_code == 400


def test_polish_publisher_tags_are_searchable(source):
    target = record(source, 'generic-title', NOW, tags=['Łódź'])
    assert ids(APIClient().get('/api/feed/', {'q': 'Łódź'}).data) == {target.pk}


def test_editorial_slots_only_published(source):
    visible = Thread.objects.create(title='Published', published=True, editorial_slot='government')
    Thread.objects.create(title='Draft', published=False, editorial_slot='government')
    Thread.objects.create(title='Unslotted', published=True)
    data = APIClient().get('/api/portal/config/').data
    assert data['editorial']['government']['id'] == visible.pk
    assert data['editorial']['opposition'] is None


def test_context_full_archive_distinct_counts_and_unknown_date(source):
    main = record(source, 'main', NOW, title='Temat', tags=['Unikalnytemat'])
    old = record(source, 'old', datetime(2001, 1, 1, tzinfo=dt_timezone.utc), title='Unikalnytemat dawniej', category='interview')
    undated = record(source, 'undated', title='Dokument', category='document')
    for suffix in ['proof1', 'proof2']:
        EvidenceLink.objects.create(article=undated, phrase='Unikalnytemat', source_url='https://example.org/' + suffix)
    record(source, 'unrelated', NOW, title='Całkiem inny nagłówek')
    data = APIClient().get(f'/api/articles/{main.pk}/context/').data
    assert data['total'] == 2
    assert {row['category']: row['count'] for row in data['counts']} == {'interview': 1, 'document': 1}
    assert data['timeline']['unknown'][0]['id'] == undated.pk
    assert data['timeline']['2001-01-01'][0]['id'] == old.pk
    assert data['complete'] is False


def test_empty_terms_do_not_invent_relations_and_count_cap(source):
    main = record(source, 'stop', NOW, title='To jest dziś')
    record(source, 'random', NOW)
    client = APIClient()
    data = client.get(f'/api/articles/{main.pk}/context/').data
    assert data['keywords'] == [] and data['total'] == 0 and data['timeline'] == {}
    assert client.get('/api/context/counts/?ids=1,2,3,4,5').status_code == 400
    assert client.get('/api/context/counts/?ids=').status_code == 400


def test_context_cache_refreshes_when_archive_generation_changes(source):
    main = record(source, 'main', NOW, tags=['Unikalnytemat'])
    client = APIClient()
    assert client.get(f'/api/articles/{main.pk}/context/').data['total'] == 0
    record(source, 'new', NOW, title='Unikalnytemat')
    from news.signals import invalidate_search
    invalidate_search()  # Simulate the transaction.on_commit signal in this test transaction.
    assert client.get(f'/api/articles/{main.pk}/context/').data['total'] == 1


def test_context_hidden_source_removed_from_counts_after_invalidation(source):
    main = record(source, 'main', NOW, tags=['Unikalnytemat'])
    other = Source.objects.create(name='Other', url='https://other.example', is_active=True)
    record(other, 'other', NOW, title='Unikalnytemat')
    client = APIClient()
    assert client.get(f'/api/articles/{main.pk}/context/').data['total'] == 1
    other.is_active = False
    other.save()
    from news.signals import invalidate_search
    invalidate_search()
    assert client.get(f'/api/articles/{main.pk}/context/').data['total'] == 0


def test_context_polish_tags_and_hidden_origin(source):
    main = record(source, 'main', NOW, title='Ogłoszenie', tags=['Łódź'])
    related = record(source, 'related', NOW, title='Dokument', tags=['Łódź'])
    client = APIClient()
    result = client.get(f'/api/articles/{main.pk}/context/').data
    assert result['total'] == 1
    assert next(iter(result['timeline'].values()))[0]['id'] == related.pk
    source.is_active = False
    source.save()
    assert client.get(f'/api/articles/{main.pk}/context/').status_code == 404


def test_polish_lowercase_query_matches_uppercase_title_and_tags(source):
    tagged = record(source, 'tagged', NOW, tags=['Łódź'])
    titled = record(source, 'titled', NOW, title='ŁÓDŹ')
    record(source, 'unrelated', NOW, tags=['Warszawa'])
    assert ids(APIClient().get('/api/feed/', {'q': 'łódź'}).data) == {tagged.pk, titled.pk}
    assert ids(APIClient().get('/api/feed/', {'q': 'łódź.*'}).data) == set()


def test_context_frequency_counts_share_one_archive_scan(source, django_assert_num_queries):
    from news.portal import context_summary
    main = record(source, 'main', NOW, title='Energia Klimat Kopalnia')
    related = record(source, 'related', NOW, title='Energia Klimat')
    for suffix in ['proof1', 'proof2']:
        EvidenceLink.objects.create(article=related, phrase='Kopalnia', source_url='https://example.org/' + suffix)
    with django_assert_num_queries(2):
        result = context_summary(main)
    assert result['total'] == 1
    assert set(result['keywords']) == {'energia', 'klimat', 'kopalnia'}
