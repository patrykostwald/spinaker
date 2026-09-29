import io
from datetime import timedelta
from unittest.mock import patch

import pytest
from PIL import Image
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from news import clinic
from news.clinic_models import SpinDiagnosis
from news.clinic_scan import model_label, scan_data
from news.techniques import CANONICAL_TECHNIQUES, FAMILIES, technique_family
from news.test_clinic import account, post


def diagnosis(acc=None, number=1, **kwargs):
    return SpinDiagnosis.objects.create(post=post(acc or account(), str(number)), status='approved',
                                       verdict='spin', intensity=55, diagnosed_at=timezone.now(), **kwargs)


def test_families():
    categories = [category for values in FAMILIES.values() for category in values]
    assert len(categories) == len(set(categories)) == 22
    assert set(categories) == set(CANONICAL_TECHNIQUES)
    assert [len(v) for v in FAMILIES.values()] == [8, 6, 7, 1]
    assert technique_family('nieznana') == 'inne'


@pytest.mark.parametrize('raw,label', [('openai/gpt-oss-20b', 'gpt-oss 20B'),
    ('qwen/qwen3.8-27b', 'Qwen 27B'), ('gemini-3.8-flash', 'Gemini Flash'), ('claude-opus-5', 'Claude')])
def test_model_labels(raw, label):
    assert model_label(raw) == label


@pytest.mark.django_db
def test_scan_and_safe_synthesis(monkeypatch):
    row = diagnosis(techniques=[{'name': 'Straszenie'}, {'name': 'Straszenie'}, {'name': 'Teza bez dowodu'}],
        claims=[{'assessment': 'supported', 'sources': [{'url': 'https://example.org'}]},
                {'assessment': 'misleading', 'sources': [{'url': 'https://example.org'}]},
                {'assessment': 'contradicted', 'sources': []}], x_thread=['Stara synteza.'],
        usage={'council': {'members': [{'model': 'openai/gpt-oss-20b', 'verdict': 'spin', 'intensity': 55}],
                           'agreement': '1/1', 'review': {'ok': False}, 'escalated': True}})
    scan = scan_data(row)
    assert scan['families'] == {'fakty': 1, 'emocje': 1, 'zagrania': 0, 'inne': 0}
    assert scan['claims'] == {'checked': 2, 'supported': 1, 'misleading': 1, 'contradicted': 0, 'unverified': 1}
    assert scan['sources'] == 1 and scan['synthesis'] is None
    assert scan['council']['reviewed'] is True
    monkeypatch.setattr(clinic.clinic_ai, 'x_thread', lambda data: {'posts': ['Bezpieczna synteza.', 'Punkt.']})
    assert clinic.ensure_x_thread(row)
    row.refresh_from_db()
    assert scan_data(row)['synthesis'] == {'lead': 'Bezpieczna synteza.', 'points': ['Punkt.']}
    assert clinic.detail_data(row)['scan'] == scan_data(row)


@pytest.mark.django_db
def test_twenty_cards_have_no_extra_queries(django_assert_num_queries):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    acc = account()
    for number in range(20):
        diagnosis(acc, number)
    # Rozgrzanie cache ContentType, wspólne dla obu pomiarów.
    clinic.cards(clinic.published_diagnoses()[:1])
    with patch('news.clinic.scan_data', return_value={}), CaptureQueriesContext(connection) as baseline:
        clinic.cards(clinic.published_diagnoses()[:20])
    with django_assert_num_queries(len(baseline)):
        cards = clinic.cards(clinic.published_diagnoses()[:20])
    assert len(cards) == 20
    row = clinic.published_diagnoses().first()
    with django_assert_num_queries(0):
        clinic.card_data(row, {})


@pytest.mark.django_db
def test_png_visibility_and_cache(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    row = diagnosis(x_thread=['Wpis wymaga kontekstu.'])
    client = APIClient()
    url = f'/api/clinic/spins/{row.pk}/card.png'
    response = client.get(url)
    payload = b''.join(response.streaming_content)
    response.close()
    assert response.status_code == 200 and response['Content-Type'] == 'image/png'
    assert response['Cache-Control'] == 'public, max-age=3600'
    assert Image.open(io.BytesIO(payload)).size == (1200, 675)
    with patch('news.clinic_card.render', side_effect=AssertionError('cache')):
        response = client.get(url)
        assert b''.join(response.streaming_content) == payload
        response.close()
    row.hidden_at = timezone.now()
    row.save()
    assert client.get(url).status_code == 404
    row.hidden_at = None
    row.status = 'pending_review'
    row.save()
    assert client.get(url).status_code == 404
    row.status = 'approved'
    row.save()
    row.post.available = False
    row.post.save()
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_backlog_command(monkeypatch):
    row = diagnosis()
    row.diagnosed_at = timezone.now() - timedelta(days=500)
    row.save()
    monkeypatch.setattr(clinic.clinic_ai, 'x_thread', lambda data: {'posts': ['Synteza.']})
    call_command('fill_x_threads', limit=50, stdout=io.StringIO())
    row.refresh_from_db()
    assert row.x_thread == ['Synteza.']


@pytest.mark.django_db
def test_scan_statistics():
    from news.clinic_stats import stats_data
    cache.clear()
    row = diagnosis(techniques=[{'name': 'Straszenie'}, {'name': 'Przesada'}],
        claims=[{'assessment': 'supported', 'sources': [{'url': 'https://example.org'}]}],
        usage={'council': {'members': [{'model': 'a', 'verdict': 'spin'}, {'model': 'b', 'verdict': 'spin'}],
                           'escalated': True}})
    row.post.source_data = {'public_metrics': {'like_count': 42}}
    row.post.save()
    result = stats_data()
    assert result['families']['emocje']['opposition'] == {'count': 1, 'enough_data': False}
    assert result['claims']['opposition']['checked'] == 1
    assert result['council']['unanimous_percent'] == 100
    assert result['council']['escalations'] == 1
    assert result['engagement']['opposition']['spin']['average_likes'] == 42
    assert result['engagement']['government']['spin']['average_likes'] is None
    cache.clear()
