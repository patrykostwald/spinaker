from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from news.models import Article, Source
from news.political_models import OfficialVideoChannel
from news.przeszlosc_paski import CACHE_KEY, strip_data
from news.public_records_models import PublicRecord

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_strip_cache():
    cache.delete(CACHE_KEY)
    yield
    cache.delete(CACHE_KEY)


def channel(key='UCtest', status='confirmed', enabled=True):
    source = Source.objects.create(name=f'Kanał {key}', url=f'https://www.youtube.com/channel/{key}')
    OfficialVideoChannel.objects.create(subject_content_type=ContentType.objects.get_for_model(Source),
        subject_object_id=source.pk, channel_url=source.url, channel_id=key, display_name=source.name,
        evidence_url='https://sejm.gov.pl/', status=status, collection_enabled=enabled)
    return source


def video(source, number, date):
    return Article.objects.create(source=source, title=f'Film {number}',
        url=f'https://www.youtube.com/watch?v={number:011d}', published_date=date,
        ingestion_method='youtube', description='Nie publikuj treści', image_url='https://obcy.example/obraz.jpg')


def record(number, date):
    return PublicRecord.objects.create(source='sejm', kind='print', external_id=str(number),
        title=f'Druk {number}', date=date, source_url=f'https://sejm.gov.pl/druki/{number}',
        text='Nie publikuj treści', data={'diagnosis': 'Nie publikuj diagnozy'})


def test_shape_neutral_metadata_and_official_thumbnail():
    video(channel(), 1, timezone.now())
    record(1, timezone.now().date())
    response = APIClient().get('/api/przeszlosc/paski/')
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {'youtube', 'publiczne', 'media', 'kategorie', 'generated_at'}
    assert data['media'] == [] and data['kategorie']['media'] == []
    assert data['youtube'][0]['image_url'] == 'https://i.ytimg.com/vi/00000000001/mqdefault.jpg'
    assert data['publiczne'][0]['kind'] == 'Druk sejmowy'
    allowed = {'id', 'title', 'date', 'source', 'url', 'category', 'category_label', 'kind', 'image_url'}
    assert all(set(row) <= allowed for name in ('youtube', 'publiczne') for row in data[name])
    assert 'Nie publikuj' not in response.content.decode()
    assert APIClient().get('/api/przeszlosc/paski/?narracja=1').json() == data


def test_latest_first_limit_and_constant_query_count(django_assert_num_queries):
    source = channel()
    now = timezone.now()
    for number in range(25):
        video(source, number, now - timedelta(days=number))
        record(number, now.date() - timedelta(days=number))
    video(source, 100, None)
    record(100, None)
    with django_assert_num_queries(3):
        data = strip_data()
    assert [row['title'] for row in data['youtube']] == [f'Film {n}' for n in range(20)]
    assert [row['title'] for row in data['publiczne']] == [f'Druk {n}' for n in range(20)]


def test_only_confirmed_enabled_active_channels():
    now = timezone.now()
    video(channel('UCpending', status='pending_review'), 1, now)
    video(channel('UCdisabled', enabled=False), 2, now)
    inactive = channel('UCinactive')
    inactive.is_active = False
    inactive.save(update_fields=['is_active'])
    video(inactive, 3, now)
    unrelated = Source.objects.create(name='Nieoficjalny', url='https://www.youtube.com/channel/UCunknown')
    video(unrelated, 4, now)
    video(channel('UCofficial'), 5, now)
    assert [row['title'] for row in strip_data()['youtube']] == ['Film 5']


def test_empty_and_cached_for_five_minutes():
    client = APIClient()
    with patch('news.przeszlosc_paski.cache.set', wraps=cache.set) as setter:
        first = client.get('/api/przeszlosc/paski/').json()
    assert first['youtube'] == first['publiczne'] == []
    assert setter.call_args.args[2] == 300
    with patch('news.przeszlosc_paski.strip_data', side_effect=AssertionError('Cache pominięty')):
        assert client.get('/api/przeszlosc/paski/').json() == first
    assert client.post('/api/przeszlosc/paski/').status_code == 405


def test_kprm_existing_articles_join_public_records_without_content():
    source = Source.objects.create(name='KPRM', url='https://www.gov.pl/web/premier')
    now = timezone.now()
    Article.objects.create(source=source, title='Komunikat KPRM', url=source.url + '/komunikat',
        published_date=now, ingestion_method='rss', description='Nie publikuj treści')
    record(1, now.date() - timedelta(days=1))
    data = strip_data()['publiczne']
    assert [row['title'] for row in data] == ['Komunikat KPRM', 'Druk 1']
    assert data[0]['kind'] == 'Komunikat' and data[0]['source'] == 'KPRM'
    assert 'description' not in data[0]


def test_category_labels_are_unique():
    from news.przeszlosc_paski import strip_data
    from news.public_records_models import PublicRecord
    for n, kind in enumerate(('print', 'unknown_a', 'unknown_b')):
        PublicRecord.objects.create(source='sejm', kind=kind, external_id=f'u{n}', title=f'Dok {n}', source_url=f'https://example.org/u{n}',
                                    response_url='https://example.org/', response_sha256='0')
    labels = [c['label'] for c in strip_data()['kategorie']['publiczne']]
    assert len(labels) == len(set(labels))
