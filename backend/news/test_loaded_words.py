import pytest
from django.core.cache import cache
from django.utils import timezone

from news.loaded_words import KINDS, ROOTS, loaded_words, loaded_data, validate_loaded_words
from news.clinic_models import SpinDiagnosis
from news.clinic_scan import scan_data
from news.clinic_stats import stats_data
from news.test_clinic import account, post


def test_inflections_order_and_duplicates():
    text = 'Katastrofą, SKANDALU, bohaterowie, krzywdzeni, nieudolność! katastrofą.'
    assert loaded_words(text) == [
        {'word': word, 'kind': kind} for word, kind in zip(
            ['Katastrofą', 'SKANDALU', 'bohaterowie', 'krzywdzeni', 'nieudolność'],
            ['strach', 'gniew', 'duma', 'litość', 'pogarda'])]
    assert all(25 <= len(roots) <= 40 for roots in ROOTS.values())


def test_exceptions_and_phrases():
    assert loaded_words('Dramat teatralny, ofiara na tacę, ofiary pieniężne. Dzieci idą do szkoły.') == []
    assert loaded_words('odebrano dzieci. Dramat mieszkańców.') == [
        {'word': 'odebrano dzieci', 'kind': 'litość'}, {'word': 'Dramat', 'kind': 'strach'}]
    assert loaded_words('Film: dramat. To skandal!') == [{'word': 'skandal', 'kind': 'gniew'}]


def test_model_validation():
    assert validate_loaded_words('Tragedia i przerósł.', [
        {'word': 'TRAGEDIA', 'kind': 'nieznany'}, {'word': 'Tragedia', 'kind': 'gniew'},
        {'word': 'zdrada', 'kind': 'gniew'}, {'word': 'przerósł', 'kind': 'pogarda'},
        {'word': 'agedia', 'kind': 'strach'}, {'word': 'i', 'kind': []}, None]) == [
            {'word': 'Tragedia', 'kind': 'strach'}, {'word': 'przerósł', 'kind': 'pogarda'}]
    assert loaded_data('Tragedia', [])['source'] == 'słownik'
    text = ' '.join(['katastrofa', 'tragedia', 'skandal', 'hańba', 'zdrada', 'oszust', 'bohater', 'patriota', 'krzywda'])
    data = loaded_data(text)
    assert data['count'] == 9 and len(data['words']) == 8
    assert sum(data['by_kind'].values()) == 9


@pytest.mark.django_db
def test_save_and_legacy_scan():
    row = SpinDiagnosis.objects.create(post=post(account(), text='Tragedia! Tragedia!'))
    assert scan_data(row)['loaded'] == {'count': 1, 'words': [{'word': 'Tragedia', 'kind': 'strach'}],
        'by_kind': {kind: int(kind == 'strach') for kind in KINDS}, 'source': 'słownik'}
    row.usage = {'loaded_words': [{'word': 'TRAGEDIA', 'kind': 'gniew'}, {'word': 'kłamstwo', 'kind': 'gniew'}]}
    row.save(update_fields=['usage'])
    row.refresh_from_db()
    assert row.usage['loaded_words'] == [{'word': 'Tragedia', 'kind': 'gniew'}]
    assert scan_data(row)['loaded']['source'] == 'model'


@pytest.mark.django_db
def test_loaded_statistics():
    cache.clear()
    acc = account()
    for i in range(10):
        SpinDiagnosis.objects.create(post=post(acc, str(i), text='Tragedia, skandal, SKANDAL!'),
            status='approved', verdict='spin', diagnosed_at=timezone.now())
    other = account('government', 'other', '102')
    SpinDiagnosis.objects.create(post=post(other, '100', text='Informacja.'),
        status='approved', verdict='no_spin', diagnosed_at=timezone.now())
    result = stats_data()['loaded']
    assert result['opposition']['average_count'] == 2
    assert result['opposition']['count'] == 10 and result['opposition']['enough_data']
    assert result['opposition']['by_kind']['gniew'] == {'count': 10, 'enough_data': True}
    assert result['government']['average_count'] == 0
    assert not result['government']['enough_data']
    cache.clear()


def test_schemas_and_council_validation(monkeypatch):
    from news import clinic_ai, clinic_council
    for schema in [clinic_ai.DIAGNOSIS_SCHEMA, clinic_council.MEMBER_SCHEMA]:
        assert 'loaded_words' not in schema['required']
        assert schema['properties']['loaded_words']['items']['properties']['kind']['enum'] == list(KINDS)
    raw = {'verdict': 'spin', 'loaded_words': [{'word': 'TRAGEDIA', 'kind': 'strach'},
                                             {'word': 'zdrada', 'kind': 'gniew'}]}
    monkeypatch.setattr(clinic_council, 'ask', lambda *a, **kw: raw)
    opinion = clinic_council._opinion(('groq', 'test'), 'Tragedia', '')
    assert opinion['loaded_words'] == [{'word': 'Tragedia', 'kind': 'strach'}]
    assert clinic_ai.clean_diagnosis(raw, 'Tragedia', {})['loaded_words'] == opinion['loaded_words']


@pytest.mark.django_db
def test_diagnosis_persists_loaded_words(monkeypatch):
    from news import clinic, clinic_ai
    from news.test_clinic import fake_diagnosis
    row = SpinDiagnosis.objects.create(post=post(account(), text='Tragedia!'))
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda context: {
        **fake_diagnosis(), 'loaded_words': [{'word': 'TRAGEDIA', 'kind': 'strach'},
                                           {'word': 'zdrada', 'kind': 'gniew'}]})
    monkeypatch.setattr(clinic, 'ensure_x_thread', lambda row: None)
    clinic.diagnose(row)
    row.refresh_from_db()
    assert row.usage['loaded_words'] == [{'word': 'Tragedia', 'kind': 'strach'}]


@pytest.mark.skip(reason="Układ karty ze zlecenia 020 — wiersz słów nacechowanych wraca w zleceniu 022")
def test_card_loaded_row_has_separate_space(monkeypatch):
    from news import clinic_card
    from news.test_clinic_scan import card_fixture
    data = card_fixture()
    data['scan']['loaded'] = loaded_data('Tragedia skandal')
    boxes = []
    original = clinic_card._text
    def capture(draw, value, box, **kwargs):
        boxes.append((str(value), box))
        return original(draw, value, box, **kwargs)
    monkeypatch.setattr(clinic_card, '_text', capture)
    monkeypatch.setattr(clinic_card, 'fetch_image', lambda url: None)
    clinic_card.render(data)
    label, box = next((value, box) for value, box in boxes if value.startswith('Słowa nacechowane:'))
    assert label == 'Słowa nacechowane: 2 · Tragedia · skandal'
    assert box[3] <= 802
    assert all(other[3] <= box[1] or other[1] >= box[3] for value, other in boxes
               if other[0] >= 652 and other != box)
