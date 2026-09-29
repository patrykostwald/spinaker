import io
from copy import deepcopy
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


def card_fixture():
    return {'id': 1041, 'verdict': 'partial', 'verdict_label': 'Częściowy spin', 'intensity': 55,
            'headline': 'Wniosek diagnozy.', 'summary': 'Uzasadnienie.',
            'author': {'name': 'Jan Kowalski', 'avatar_url': '', 'party': {'short': 'ABC'}},
            'post': {'text': 'Treść wpisu.', 'published_at': '2026-09-28', 'media': []},
            'scan': {'scope': {}, 'families': {}, 'claims': {}, 'council': {}, 'synthesis': None}}


@pytest.mark.parametrize('url', ['https://example.com/x.png', 'http://pbs.twimg.com/a',
    'https://pbs.twimg.com.evil.org/a', 'https://pbs.twimg.com@evil.org/a',
    'https://pbs.twimg.com:444/a', 'file:///tmp/a'])
def test_card_rejects_media_hosts(url):
    from news.clinic_card import fetch_image
    with patch('news.clinic_card.requests.get') as get:
        assert fetch_image(url) is None
        get.assert_not_called()


def test_card_media_cache_and_limits(settings, tmp_path):
    from unittest.mock import MagicMock
    from news.clinic_card import fetch_image, MAX_BYTES
    settings.MEDIA_ROOT = tmp_path
    stream = io.BytesIO()
    Image.new('RGB', (20, 20)).save(stream, 'PNG')
    response = MagicMock(status_code=200, headers={})
    response.__enter__.return_value = response
    response.iter_content.return_value = [stream.getvalue()]
    with patch('news.clinic_card.requests.get', return_value=response) as get:
        for _ in range(2):
            assert fetch_image('https://pbs.twimg.com/good').size == (20, 20)
        get.assert_called_once_with('https://pbs.twimg.com/good', stream=True, timeout=5, allow_redirects=False)
    for name, status, chunks in [('redirect', 302, []), ('large', 200, [b'x' * (MAX_BYTES + 1)]), ('invalid', 200, [b'bad'])]:
        response.status_code = status
        response.iter_content.return_value = chunks
        with patch('news.clinic_card.requests.get', return_value=response) as get:
            assert fetch_image(f'https://pbs.twimg.com/{name}') is None
            assert fetch_image(f'https://pbs.twimg.com/{name}') is None
            assert get.call_count == 1


@pytest.mark.parametrize('card_format', ['diagnoza', 'skrot'])
def test_card_deleted_omits_text_and_attachment(card_format):
    from news.clinic_card import render
    data = card_fixture()
    data['post'].update(available=False, text='TAJNA TREŚĆ', media=[{'url': 'https://pbs.twimg.com/secret'}])
    clean = deepcopy(data)
    clean['post'].update(text='', media=[])
    data['scan']['techniques'] = [{'quote': 'TAJNY CYTAT'}]
    with patch('news.clinic_card.fetch_image', return_value=None) as fetch:
        assert render(data, card_format) == render(clean, card_format)
    assert all(call.args == ('',) for call in fetch.call_args_list)


@pytest.mark.parametrize('card_format', ['diagnoza', 'skrot'])
def test_card_long_text_stays_in_boxes_and_does_not_overlap(card_format):
    from news import clinic_card
    from PIL import ImageDraw
    data = card_fixture()
    data['author']['name'] = 'Bardzo długie nazwisko ' * 30
    data['headline'] = 'Długi wniosek diagnozy ' * 80
    data['summary'] = 'Obszerne uzasadnienie ' * 70
    data['post']['text'] = 'https://example.org/' + 'x' * 600 + ' długi wpis' * 100
    boxes, bounds = [], []
    original_text, original_draw = clinic_card._text, ImageDraw.ImageDraw.text
    def field(draw, value, box, **kwargs):
        boxes.append(box)
        try:
            return original_text(draw, value, box, **kwargs)
        finally:
            boxes.pop()
    def record(self, xy, text, *args, **kwargs):
        bound = self.textbbox(xy, text, font=kwargs['font'], anchor=kwargs['anchor'])
        x, y, right, bottom = boxes[-1]
        assert x <= bound[0] and y <= bound[1] and bound[2] <= right and bound[3] <= bottom
        for other in bounds:
            assert bound[2] <= other[0] or bound[0] >= other[2] or bound[3] <= other[1] or bound[1] >= other[3]
        bounds.append(bound)
        return original_draw(self, xy, text, *args, **kwargs)
    with patch('news.clinic_card.fetch_image', return_value=None), patch.object(clinic_card, '_text', field), patch.object(ImageDraw.ImageDraw, 'text', record):
        assert Image.open(io.BytesIO(clinic_card.render(data, card_format))).size == (1600, 900)


def test_card_attachment_fills_column_bottom():
    from news.clinic_card import render
    data = card_fixture()
    data['post']['media'] = [{'url': 'https://pbs.twimg.com/photo'}]
    with patch('news.clinic_card.fetch_image', side_effect=[None, Image.new('RGB', (300, 900), '#ff0000')]):
        image = Image.open(io.BytesIO(render(data)))
    assert image.getpixel((300, 801)) == (255, 0, 0)


def diagnosis(acc=None, number=1, **kwargs):
    return SpinDiagnosis.objects.create(post=post(acc or account(), str(number)), status='approved',
                                       verdict='spin', intensity=55, diagnosed_at=timezone.now(), **kwargs)


def test_families():
    categories = [category for values in FAMILIES.values() for category in values]
    assert len(categories) == len(set(categories)) == 22
    assert set(categories) == set(CANONICAL_TECHNIQUES)
    assert [len(v) for v in FAMILIES.values()] == [10, 6, 5, 1]
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
    assert scan['families'] == {k: {'technique_types': v} for k, v in {'dane': 1, 'przedstawienie': 1, 'spor': 0, 'inne': 0}.items()}
    assert scan['claims'] == {'checked': 2, 'supported': 1, 'misleading': 1, 'contradicted': 0, 'unverified': 1, 'opinions': 0, 'distinct': 3}
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
    assert Image.open(io.BytesIO(payload)).size == (1600, 900)
    with patch('news.clinic_card.render', side_effect=AssertionError('cache')):
        response = client.get(url)
        assert b''.join(response.streaming_content) == payload
        response.close()
    short = client.get(url + '?format=skrot')
    short_payload = b''.join(short.streaming_content)
    short.close()
    assert short.status_code == 200
    assert Image.open(io.BytesIO(short_payload)).size == (1600, 900)
    assert short_payload != payload
    assert len(list((tmp_path / 'clinic_cards').glob('diagnosis-*.png'))) == 2
    with patch('news.clinic_card.render', side_effect=AssertionError('cache')):
        for suffix, expected in [('', payload), ('?format=diagnoza', payload), ('?format=skrot', short_payload)]:
            response = client.get(url + suffix)
            assert b''.join(response.streaming_content) == expected
            response.close()
    assert client.get(url + '?format=unknown').status_code == 400
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
    assert result['families']['przedstawienie']['opposition'] == {'count': 1, 'enough_data': False}
    assert result['claims']['opposition']['checked'] == 1
    assert result['council']['unanimous_percent'] == 100
    assert result['council']['escalations'] == 1
    assert result['engagement']['opposition']['spin']['average_likes'] == 42
    assert result['engagement']['government']['spin']['average_likes'] is None
    cache.clear()


def claim(text, assessment='supported', url='https://www.example.org/a'):
    return {'claim': text, 'assessment': assessment, 'sources': [{'url': url}] if url else []}


@pytest.mark.django_db
def test_audit_1041_duplicates():
    row = diagnosis(claims=[
        claim('Kurtki nie chronią żołnierzy przed zimnem.'),
        claim('„Kurtki nie chronią żołnierzy przed zimnem!”', url='https://example.org/b'),
        claim('Program obejmuje wyłącznie slajdy.', 'contradicted', 'https://second.org/a'),
        claim('Nie dostarczono żadnego sprzętu.', 'contradicted'),
        claim('To wielka porażka polityczna.', 'unverified', ''),
        claim('Minister zasługuje na krytykę.', 'unverified', '')])
    scan = scan_data(row)
    assert scan['claims'] == dict(supported=1, misleading=0, contradicted=2,
                                 checked=3, opinions=2, distinct=5, unverified=0)
    assert scan['sources'] == 2
    assert scan['source_domains'] == ['example.org', 'second.org']


@pytest.mark.django_db
def test_audit_1060_three_pairs():
    row = diagnosis(claims=[
        claim('Firmy paliwowe osiągnęły rekordowe zyski w ubiegłym roku.'),
        claim('Firmy paliwowe osiągnęły rekordowe zyski w ubiegłym roku według raportu.'),
        claim('Podatek obejmuje okres od stycznia do grudnia.'),
        claim('Podatek obejmuje okres od stycznia do grudnia 2025 roku.'),
        claim('Projekt prezydencki pomija kryterium dochodowe gospodarstw domowych.', 'misleading'),
        claim('Projekt prezydencki pomija kryterium dochodowe gospodarstw.', 'contradicted')])
    scan = scan_data(row)
    assert scan['claims']['distinct'] == scan['claims']['checked'] == 3
    assert scan['claims']['supported'] == 2
    assert scan['claims']['contradicted'] == 1


@pytest.mark.django_db
@pytest.mark.parametrize('kind', ['video', 'animated_gif', 'amplify_video_thumb'])
def test_scope_council_and_share(kind):
    from news.x_share import weight
    row = diagnosis(x_thread=['Krótki wniosek.'], usage={'council': {'members': [
        {'verdict': 'spin', 'intensity': 55}, {'verdict': 'spin', 'intensity': 75},
        {'verdict': 'partial', 'intensity': 55}]}})
    row.post.media = [{'type': 'photo'}, {'type': kind}]
    scan = scan_data(row)
    assert scan['scope'] == dict(text=True, image=True, video=False,
                                 analyzed=['tekst', 'obraz'], not_analyzed=['film'])
    assert scan['council']['verdict_agreement'] == '2/3'
    assert scan['council']['range'] == [55, 75]
    assert weight(scan['share']['single']) <= 220
    assert f'/klinika/{row.pk}' in scan['share']['single']
    row.x_thread = ['Bardzo długi tekst ' * 100 + '.']
    row.post.account.display_name = 'Nazwisko' * 100
    assert weight(scan_data(row)['share']['single']) <= 220


@pytest.mark.django_db
def test_selection_pool_includes_all_published_verdicts():
    row = diagnosis()
    other = diagnosis(row.post.account, 2)
    other.verdict = 'no_spin'
    other.save()
    result = clinic.spin_of_day_by_camp()['spins']['opposition']
    assert result['id'] == row.pk
    assert result['pool'] == 2
    assert result['window_label'] in ('dzisiaj', 'ostatnia doba')


def test_merge_priority_sources_and_missing_text():
    from news.clinic_scan import merge_claims
    items = [claim('Ta sama teza.', 'supported', 'https://example.org/a'),
             claim('TA SAMA TEZA!', 'misleading', 'https://example.org/b'),
             claim('Ta sama teza', 'contradicted', 'https://other.org/a')]
    merged = merge_claims(items)
    assert len(merged) == 1
    assert merged[0]['assessment'] == 'contradicted'
    assert len(merged[0]['sources']) == 3
    assert items[0]['assessment'] == 'supported'
    assert len(merge_claims([claim(''), claim('')])) == 2


def test_short_quote_and_complete_reason():
    from news.clinic_card import _quote, _short_reason, _wrap
    from news.x_card import _font
    from PIL import ImageDraw
    data = card_fixture()
    data['scan']['techniques'] = [{'quote': ' '.join(f'word{i}' for i in range(40))}]
    assert _quote(data) == ' '.join(f'word{i}' for i in range(25)) + '…'
    data['scan']['techniques'] = []
    assert _quote(data) == data['post']['text']
    draw = ImageDraw.Draw(Image.new('RGB', (1600, 900)))
    long = 'Bardzo długie zdanie ' * 80 + '.'
    reason = _short_reason(draw, long, 'Krótkie pełne zdanie. Następne zdanie.', 864)
    assert reason == 'Krótkie pełne zdanie.'
    assert len(_wrap(draw, reason, _font(17), 864)) <= 2
    assert _short_reason(draw, long, long, 864) == ''
