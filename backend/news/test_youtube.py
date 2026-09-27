import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.test import APIClient

from news.models import Article, Source


def staff_client():
    client = APIClient()
    client.force_authenticate(get_user_model().objects.create_user('zespol', password='x', is_staff=True))
    return client


@pytest.mark.django_db
def test_youtube_disabled_without_network(monkeypatch, settings):
    settings.YOUTUBE_ENABLED = False
    monkeypatch.setattr('news.youtube.requests.get', lambda *a, **k: pytest.fail('Unexpected network'))
    assert staff_client().post('/api/youtube/search/', {'q': 'test'}, format='json').json()['status'] == 'not_configured'
    assert Article.objects.count() == 0


@pytest.mark.django_db
def test_youtube_search_is_staff_only(monkeypatch, settings):
    settings.YOUTUBE_ENABLED = True; settings.YOUTUBE_API_KEY = 'test-only'
    monkeypatch.setattr('news.youtube.requests.get', lambda *a, **k: pytest.fail('Unexpected network'))
    assert APIClient().post('/api/youtube/search/', {'q': 'test'}, format='json').status_code in (401, 403)


@pytest.mark.django_db
def test_youtube_search_saves_nothing_cache_and_budget(monkeypatch, settings):
    cache.clear()
    settings.YOUTUBE_ENABLED = True; settings.YOUTUBE_API_KEY = 'test-only'; settings.YOUTUBE_DAILY_REQUEST_LIMIT = 1
    class Result:
        def raise_for_status(self): pass
        def json(self):
            return {'items': [{'id': {'videoId': 'abcdefghijk'}, 'snippet': {'title': 'Dokument', 'channelId': 'UCtest', 'channelTitle': 'Test channel', 'publishedAt': '2020-01-01T10:00:00Z'}}], 'nextPageToken': 'page2'}
    monkeypatch.setattr('news.youtube.requests.get', lambda *a, **k: Result())
    client = staff_client()
    first = client.post('/api/youtube/search/', {'q': 'Dokument'}, format='json')
    assert first.status_code == 200
    assert first.json()['articles'][0]['channel'] == 'Test channel' and first.json()['next_token'] == 'page2'
    # Wynik wyszukiwania z dowolnego kanału nie staje się źródłem ani materiałem w bazie.
    assert Article.objects.count() == 0 and Source.objects.count() == 0
    assert client.post('/api/youtube/search/', {'q': 'Dokument'}, format='json').status_code == 200
    assert client.post('/api/youtube/search/', {'q': 'Inna fraza'}, format='json').status_code == 429
    cache.clear()


@pytest.mark.django_db
def test_unofficial_youtube_channels_are_hidden_not_deleted():
    meme = Source.objects.create(name='PRAW(d)A', url='https://www.youtube.com/channel/UCmeme', source_type='portal', scrape_enabled=False)
    Article.objects.create(source=meme, title='Przeróbka', url='https://www.youtube.com/watch?v=abcdefghijk', category='video', ingestion_method='youtube')
    call_command('hide_unofficial_youtube_sources')  # bez --apply: tylko raport
    meme.refresh_from_db()
    assert meme.is_active
    call_command('hide_unofficial_youtube_sources', '--apply')
    meme.refresh_from_db()
    assert not meme.is_active and meme.catalog_stage == 'excluded' and Article.objects.count() == 1


@pytest.mark.django_db
def test_official_channel_collection_and_leftover_quota(monkeypatch, settings):
    from django.contrib.contenttypes.models import ContentType
    from news import youtube_collect
    from news.political_models import OfficialVideoChannel
    settings.YOUTUBE_ENABLED = True; settings.YOUTUBE_API_KEY = 'test-only'; settings.YOUTUBE_DAILY_UNITS = 305
    office = Source.objects.create(name='Kancelaria', url='https://example.gov.pl/')
    OfficialVideoChannel.objects.create(subject_content_type=ContentType.objects.get_for_model(Source), subject_object_id=office.pk,
        channel_url='https://www.youtube.com/channel/UCofficial', channel_id='UCofficial', display_name='Kancelaria',
        evidence_url='https://example.gov.pl/kontakt', status='confirmed', collection_enabled=True)
    pages = iter(range(1, 100))
    class Result:
        def __init__(self, params): self.params = params
        def raise_for_status(self): pass
        def json(self):
            page = next(pages)
            return {'items': [{'snippet': {'title': f'Film {page}', 'channelTitle': 'Kancelaria', 'publishedAt': '2026-09-01T10:00:00Z'},
                               'contentDetails': {'videoId': f'vid{page:08d}'}}], 'nextPageToken': 'next' if page < 4 else ''}
    monkeypatch.setattr('news.youtube_collect.requests.get', lambda url, params, timeout: Result(params))
    assert youtube_collect.collect_latest()['saved'] == 1
    # Reszta limitu: kolejne strony archiwum, aż kanał się skończy (tu 3 strony) albo zostanie tylko zapas.
    result = youtube_collect.backfill_leftover(reserve=5)
    assert result['pages'] == 3 and Article.objects.filter(ingestion_method='youtube').count() == 4
    assert youtube_collect.units_used() == 4
    source = Source.objects.get(url='https://www.youtube.com/channel/UCofficial')
    assert source.is_active and source.catalog_stage == 'configured'


@pytest.mark.django_db
def test_seed_official_channels_confirms_with_evidence_and_staff(monkeypatch, settings):
    from news.management.commands import seed_official_youtube_channels as seed
    from news.political_models import OfficialVideoChannel
    settings.YOUTUBE_ENABLED = True; settings.YOUTUBE_API_KEY = 'test-only'
    get_user_model().objects.create_user('zespol', password='x', is_staff=True)
    monkeypatch.setattr(seed, 'CHANNELS', [('Senat RP', 'https://www.youtube.com/channel/UCsenat', 'https://www.senat.gov.pl/', True),
                                           ('Sejm RP', 'https://www.youtube.com/@SejmRP_PL', 'https://www.sejm.gov.pl/', False)])
    monkeypatch.setattr(seed, 'resolve', lambda url: ('UCsenat', 'Senat') if 'senat' in url else ('UCsejm', 'Sejm'))
    call_command('seed_official_youtube_channels', '--staff', 'zespol')
    assert OfficialVideoChannel.objects.count() == 0  # podgląd niczego nie zapisuje
    call_command('seed_official_youtube_channels', '--staff', 'zespol', '--apply')
    senat, sejm = OfficialVideoChannel.objects.get(channel_id='UCsenat'), OfficialVideoChannel.objects.get(channel_id='UCsejm')
    assert senat.status == 'confirmed' and senat.collection_enabled and senat.reviewed_by.username == 'zespol'
    assert sejm.status == 'pending_review' and not sejm.collection_enabled
    assert Source.objects.get(url='https://www.youtube.com/channel/UCsenat').is_active
    assert not Source.objects.get(url='https://www.youtube.com/channel/UCsejm').is_active
    call_command('seed_official_youtube_channels', '--staff', 'zespol', '--apply')  # ponownie: bez duplikatów
    assert OfficialVideoChannel.objects.count() == 2


def test_channel_link_lookups():
    from news.management.commands.seed_official_youtube_channels import lookups
    assert lookups('https://www.youtube.com/channel/UCabc') == [{'id': 'UCabc'}]
    assert lookups('https://www.youtube.com/@KObywatelska') == [{'forHandle': '@KObywatelska'}]
    assert lookups('https://www.youtube.com/user/pisorgpl')[0] == {'forUsername': 'pisorgpl'}
    assert lookups('https://www.youtube.com/premierRP')[0] == {'forHandle': '@premierRP'}


def test_social_links_from_a_source_homepage():
    from news.source_social import links_on_page
    html = b'''<a href="https://www.youtube.com/@RadioZET">YT</a><a href="https://www.youtube.com/watch?v=abc">film</a>
    <a href="https://twitter.com/RadioZET_NEWS">X</a><a href="https://x.com/intent/tweet?text=a">share</a>
    <a href="https://x.com/radiozet_news/status/1">post</a><a href="https://x.com/NawrockiKn/status/2">cytat</a>'''
    assert links_on_page(html, 'https://radiozet.pl/') == {'youtube': ['https://www.youtube.com/@RadioZET'], 'x': ['RadioZET_NEWS']}


@pytest.mark.django_db
def test_source_channels_are_queued_then_confirmed_by_staff(monkeypatch, settings):
    from news import source_social
    from news.management.commands import discover_source_social_links as discover_cmd
    from news.political_models import OfficialVideoChannel
    settings.YOUTUBE_ENABLED = True; settings.YOUTUBE_API_KEY = 'test-only'
    get_user_model().objects.create_user('zespol', password='x', is_staff=True)
    radio = Source.objects.create(name='Radio ZET', url='https://radiozet.pl/')
    from news.models import ImportState
    def fake_discover(source, network):
        result = {'status': 'ok', 'evidence_url': source.url, 'youtube': ['https://www.youtube.com/@RadioZET'],
                  'x': ['RadioZET_NEWS'], 'checked_at': '2026-09-27T10:00:00+00:00'}
        ImportState.objects.update_or_create(name=f'source-social:{source.pk}', defaults={'cursor': result})
        return result
    monkeypatch.setattr(source_social, 'discover', fake_discover)
    monkeypatch.setattr(discover_cmd, 'resolve', lambda link: ('UCradiozet', 'Radio ZET'))
    call_command('discover_source_social_links')
    assert OfficialVideoChannel.objects.count() == 0  # bez --apply tylko dowody
    call_command('discover_source_social_links', '--apply', '--force')
    row = OfficialVideoChannel.objects.get()
    assert row.status == 'pending_review' and row.subject_object_id == radio.pk and not row.collection_enabled
    call_command('confirm_source_youtube_channels', '--staff', 'zespol', '--apply')
    row.refresh_from_db()
    assert row.status == 'confirmed' and row.collection_enabled
    assert Source.objects.get(url='https://www.youtube.com/channel/UCradiozet').is_active
    call_command('confirm_source_youtube_channels', '--staff', 'zespol', '--revert', 'UCradiozet', '--apply')
    row.refresh_from_db()
    assert row.status == 'pending_review' and not row.collection_enabled
    # Kanał dodany ręcznie (bez dowodu ze strony źródła) nie jest potwierdzany automatycznie.
    manual = Source.objects.create(name='Sejm RP', url='https://www.youtube.com/channel/UCsejm', is_active=False)
    OfficialVideoChannel.objects.create(subject_content_type=row.subject_content_type, subject_object_id=manual.pk,
        channel_url='https://www.youtube.com/channel/UCsejm', channel_id='UCsejm', display_name='Sejm RP',
        evidence_url='https://www.sejm.gov.pl/', status='pending_review')
    call_command('confirm_source_youtube_channels', '--staff', 'zespol', '--apply')
    assert OfficialVideoChannel.objects.get(channel_id='UCsejm').status == 'pending_review'


@pytest.mark.django_db
def test_feed_first_page_is_diverse_across_sources():
    from datetime import timedelta
    from django.utils import timezone
    loud = Source.objects.create(name='Kanał A', url='https://a.example/')
    quiet = Source.objects.create(name='Radio B', url='https://b.example/')
    other = Source.objects.create(name='Gazeta C', url='https://c.example/')
    now = timezone.now()
    for index in range(10):  # jedno źródło publikuje dużo i najnowsze
        Article.objects.create(source=loud, title=f'A{index}', url=f'https://a.example/{index}', published_date=now - timedelta(minutes=index))
    Article.objects.create(source=quiet, title='B0', url='https://b.example/0', published_date=now - timedelta(hours=2))
    Article.objects.create(source=other, title='C0', url='https://c.example/0', published_date=now - timedelta(hours=3))
    plain = APIClient().get('/api/feed/?page_size=3').json()['results']
    assert [row['title'] for row in plain] == ['A0', 'A1', 'A2']
    mixed = APIClient().get('/api/feed/?page_size=3&diverse=1').json()['results']
    assert [row['title'] for row in mixed] == ['A0', 'B0', 'C0']
