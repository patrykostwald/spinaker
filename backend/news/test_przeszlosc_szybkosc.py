"""Śledczy R1: P1-9 (cache, rozgrzewanie, indeksy, szybsze zapytania) i P1-3 (głosowania tematu: strony, zakres dat, drzewo)."""
import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from news import przeszlosc_cache as pc
from news.models import ImportState
from news.przeszlosc import TOPICS_STATE, _match, topic_votes, topic_votes_page
from news.test_przeszlosc_osoba import mp, voting

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    monkeypatch.delenv('PRZESZLOSC_CACHE', raising=False)
    cache.clear()
    yield
    cache.clear()


def many_votings(count, mp_id=77):
    """Głosowania 1..count: rosnące id, malejące daty (n dni wstecz), wszystkie o VAT."""
    return [voting(n, [(mp_id, 'Anna Kowalska', 'KO', 'YES' if n % 2 else 'NO')]) for n in range(1, count + 1)]


# --- P1-3: dopasowanie, strony, zakres dat ---
def test_match_handles_o_alternation_and_keeps_acronym_word_boundary():
    from news.models import Article, Source
    source = Source.objects.create(name='Redakcja', url='https://media.example')
    Article.objects.create(source=source, title='Kopalnia Turowa zostaje', url='https://m.example/1', published_date=timezone.now())
    Article.objects.create(source=source, title='Vatican i podatki', url='https://m.example/2', published_date=timezone.now())
    Article.objects.create(source=source, title='Stawka VAT w górę', url='https://m.example/3', published_date=timezone.now())
    assert [a.title for a in Article.objects.filter(_match(['title'], ['Turów']))] == ['Kopalnia Turowa zostaje']
    assert [a.title for a in Article.objects.filter(_match(['title'], ['VAT']))] == ['Stawka VAT w górę']


def test_topic_votes_page_sorts_by_date_and_pages_and_filters_dates():
    many_votings(12)
    first = topic_votes_page('VAT', page=1, per_page=5)
    assert first['total'] == 12 and first['pages'] == 3 and first['page'] == 1
    assert [v['id'] for v in first['results']] == [f'10/40/{n}' for n in range(1, 6)]  # najnowsze (1 dzień wstecz) pierwsze
    assert first['range']['last'] == (timezone.now() - timezone.timedelta(days=1)).date().isoformat()
    assert first['range']['first'] == (timezone.now() - timezone.timedelta(days=12)).date().isoformat()
    last = topic_votes_page('VAT', page=9, per_page=5)
    assert last['page'] == 3 and [v['id'] for v in last['results']] == ['10/40/11', '10/40/12']
    since = (timezone.now() - timezone.timedelta(days=4)).date().isoformat()
    until = (timezone.now() - timezone.timedelta(days=2)).date().isoformat()
    ranged = topic_votes_page('VAT', since=since, until=until)
    assert ranged['total'] == 3 and ranged['filter'] == {'since': since, 'until': until}
    assert topic_votes('VAT', limit=2, offset=10) and len(topic_votes('VAT', limit=2, offset=10)) == 2
    assert topic_votes_page('lotnisko')['total'] == 0 and topic_votes_page('lotnisko')['range'] == {'first': None, 'last': None}


def test_topic_votes_endpoint_validates_and_pages():
    many_votings(10)
    client = APIClient()
    data = client.get('/api/przeszlosc/temat/glosowania/?q=VAT&strona=2&na_strone=4').json()
    assert data['topic'] == 'VAT' and data['total'] == 10 and data['page'] == 2 and len(data['results']) == 4
    assert data['results'][0]['members'] == [['Anna Kowalska', 'KO', 'za']]
    assert client.get('/api/przeszlosc/temat/glosowania/?q=VAT&strona=x').status_code == 400
    assert client.get('/api/przeszlosc/temat/glosowania/?q=VAT&od=2026-13-01').status_code == 400
    assert client.get('/api/przeszlosc/temat/glosowania/?q=VAT&od=2026-02-01&do=2026-01-01').status_code == 400
    assert client.get('/api/przeszlosc/temat/glosowania/?q=a').status_code == 400
    capped = client.get('/api/przeszlosc/temat/glosowania/?q=VAT&na_strone=500').json()
    assert capped['per_page'] == 50


def test_topic_payload_carries_total_and_range_but_only_first_page():
    many_votings(10)
    data = APIClient().get('/api/przeszlosc/temat/?q=VAT').json()
    assert len(data['votes']) == 8 and data['votes_total'] == 10 and data['counts']['vote'] == 10
    assert data['votes_range']['last'] > data['votes_range']['first']


def test_person_tree_shows_newest_votes_by_date_and_at_most_50_nodes():
    from news import przeszlosc_przeplyw as flow
    figure = mp('Anna Kowalska', 77)
    many_votings(60)
    data = APIClient().get(f'/api/przeszlosc/przeplyw/osoba:{figure.pk}/').json()
    votes = [n for n in data['nodes'] if n['kind'] == 'vote']
    assert len(votes) == flow.VOTE_NODES == 50
    dates = [n['date'] for n in votes]
    assert dates == sorted(dates, reverse=True)  # najnowsze pierwsze, po dacie
    assert dates[0] == (timezone.now() - timezone.timedelta(days=1)).date().isoformat()
    grouped = {g['kind']: g['count'] for g in data['limits']['grouped']}
    assert grouped['vote'] == 10 and data['limits']['truncated'] is True


# --- P1-9: cache, rozgrzewanie, indeksy ---
def test_cache_inactive_on_sqlite_unless_forced(monkeypatch):
    assert connection.vendor == 'sqlite'
    assert pc.active() is False
    monkeypatch.setenv('PRZESZLOSC_CACHE', 'always')
    assert pc.active() is True
    monkeypatch.setenv('PRZESZLOSC_CACHE', 'never')
    assert pc.active() is False


def test_cached_topic_serves_second_read_without_queries(monkeypatch, django_assert_num_queries):
    monkeypatch.setenv('PRZESZLOSC_CACHE', 'always')
    many_votings(3)
    first = pc.cached_topic('VAT')
    assert first['votes_total'] == 3
    with django_assert_num_queries(0):
        assert pc.cached_topic('vat  ') == first  # ten sam klucz po normalizacji wielkości liter i spacji
    page = pc.cached_topic_votes('VAT', 1, 8, None, None)
    assert page['total'] == 3
    with django_assert_num_queries(0):
        assert pc.cached_topic_votes('VAT', 1, 8, None, None) == page
    assert cache.get(pc.topic_key('VAT')) is not None


def test_empty_topic_is_cached_too(monkeypatch):
    monkeypatch.setenv('PRZESZLOSC_CACHE', 'always')
    data = pc.cached_topic('xqzw')
    assert pc.is_empty(data) and cache.get(pc.topic_key('xqzw')) == data


def test_cached_person_and_view_use_same_key(monkeypatch, django_assert_num_queries):
    monkeypatch.setenv('PRZESZLOSC_CACHE', 'always')
    figure = mp('Anna Kowalska', 77)
    many_votings(2)
    payload = pc.cached_person(figure)
    assert payload['votes']['count'] == 2 and 'mentions' not in payload and 'access' not in payload
    with django_assert_num_queries(0):
        assert pc.cached_person(figure) == payload
    data = APIClient().get(f'/api/przeszlosc/osoba/{figure.pk}/').json()
    assert data['votes']['count'] == 2 and 'mentions' in data and 'access' in data
    pc.forget_person(figure)
    assert cache.get(pc.person_key(figure)) is None


def test_warm_fills_hot_topics_and_people_within_budget(monkeypatch):
    monkeypatch.setenv('PRZESZLOSC_CACHE', 'always')
    figure = mp('Anna Kowalska', 77)
    many_votings(2)
    state, _ = ImportState.objects.get_or_create(name=TOPICS_STATE)
    state.cursor = {'topics': [{'topic': 'VAT', 'edges': 3}]}
    state.save(update_fields=['cursor'])
    from news.przeszlosc_osoba import remember_topics
    remember_topics([{'topic': 'VAT', 'people': [figure.pk]}])
    stats = pc.warm('hot')
    assert stats['topics'] >= 1 and stats['people'] == 1 and stats['errors'] == 0
    assert cache.get(pc.topic_key('VAT'))['votes_total'] == 2
    assert cache.get(pc.person_key(figure))['votes']['count'] == 2
    assert cache.get(pc.LAST_WARM_KEY)['scope'] == 'hot'
    cache.clear()
    clock = iter([0, 0, 100, 100, 100, 100])
    starved = pc.warm('all', budget_seconds=10, now=lambda: next(clock))
    assert starved['skipped'] >= 1 and starved['topics'] + starved['people'] <= 1


def test_warm_is_noop_without_cache_and_tasks_respect_switch(monkeypatch):
    assert pc.warm('hot') == {'scope': 'hot', 'topics': 0, 'people': 0, 'skipped': 0, 'errors': 0, 'disabled': True}
    from news import tasks
    from news.daily_schedule import BEAT_PLAN
    assert BEAT_PLAN['przeszlosc-warm-hot'][0] == 'przeszlosc_warm_task' and BEAT_PLAN['przeszlosc-warm-all'][0] == 'przeszlosc_warm_all_task'
    assert hasattr(tasks, 'przeszlosc_warm_task') and hasattr(tasks, 'przeszlosc_warm_all_task')
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'false')
    assert tasks.przeszlosc_warm_task() == {'status': 'disabled'}
    assert tasks.przeszlosc_warm_all_task() == {'status': 'disabled'}


def test_indeksy_command_creates_btree_indexes_and_lists_them(capsys):
    from news.management.commands.przeszlosc_indeksy import statements
    sqlite_sql = statements('sqlite')
    assert len(sqlite_sql) == 2 and all(s.startswith('CREATE INDEX IF NOT EXISTS przeszlosc_') for s in sqlite_sql)
    pg_sql = statements('postgresql')
    assert 'CREATE EXTENSION IF NOT EXISTS pg_trgm' in pg_sql
    assert all('CONCURRENTLY' in s for s in pg_sql if s.startswith('CREATE INDEX'))
    assert any('USING gin (upper(title) gin_trgm_ops)' in s and 'news_article' in s for s in pg_sql)
    call_command('przeszlosc_indeksy')
    call_command('przeszlosc_indeksy', '--sprawdz')
    out = capsys.readouterr().out
    assert 'przeszlosc_ballot_mp_voting_idx' in out and 'przeszlosc_recordperson_mp_term_idx' in out
    call_command('przeszlosc_indeksy')  # powtórka bez błędu (IF NOT EXISTS)


def test_rozgrzej_command_reports(capsys, monkeypatch):
    call_command('przeszlosc_rozgrzej')
    out = capsys.readouterr().out
    assert 'nieaktywny' in out and 'scope=hot' in out
