from datetime import timedelta

import pytest
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework.test import APIClient

from news import clinic
from news.clinic_models import SpinDiagnosis
from news.clinic_stats import CACHE_KEY, stats_data
from news.political_models import (PublicFigure, PublicFigureRole, ParliamentaryRosterEntry,
                                   PoliticalAccountCandidate, SocialHandleEvidence)
from news.techniques import CANONICAL_TECHNIQUES, canonical_technique
from news.test_clinic import account, post


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.parametrize('name,expected', [
    ('Liczby bez punktu odniesienia', 'Liczba bez punktu odniesienia'),
    ('liczba_bez_odniesienia', 'Liczba bez punktu odniesienia'),
    ('fałszywa alternatywa', 'Fałszywa alternatywa'),
    ('wybiórczość', 'Wybiórcze dane'),
    ('Słomiana kukła', 'Słomiany człowiek'),
    ('Fałszywa przyczyna', 'Fałszywa przyczynowość'),
    ('Dowód, którego nie pokazano', 'Teza bez dowodu'),
    ('Sukces bez kontekstu', 'Pominięcie kontekstu'),
    ('Atak ad hominem', 'Atak na osobę'),
    ('Odwracanie uwagi', 'Zmiana tematu'),
    ('Autorytet bez źródła', 'Odwołanie do autorytetu'),
    ('Wniosek mocniejszy niż przesłanki', 'Przesada'),
    ('ok', 'Inne'), ('', 'Inne'), (None, 'Inne'),
])
def test_techniques(name, expected):
    assert canonical_technique(name) == expected


def test_all_canonical_names():
    assert len(CANONICAL_TECHNIQUES) == 22
    for name in CANONICAL_TECHNIQUES:
        assert canonical_technique(name) == name


def test_category_prompts_and_schemas():
    from news import clinic_ai, clinic_council, clinic_interview
    from news.techniques import DEFINITIONS

    assert set(DEFINITIONS) == set(CANONICAL_TECHNIQUES)
    for prompt, schema in (
        (clinic_ai.DIAGNOSIS_SYSTEM, clinic_ai.DIAGNOSIS_SCHEMA['properties']['techniques']['items']),
        (clinic_council.MEMBER_SYSTEM, clinic_council.MEMBER_SCHEMA['properties']['techniques']['items']),
        (clinic_interview.INTERVIEW_SYSTEM, clinic_interview._TECHNIQUE),
    ):
        assert schema['properties']['category']['enum'] == list(CANONICAL_TECHNIQUES)
        assert 'category' in schema['required'] and 'name' in schema['required']
        for category in CANONICAL_TECHNIQUES:
            assert f'{category}: {DEFINITIONS[category]}' in prompt


@pytest.mark.parametrize('category', [None, '', 'Nieznana', [], {}])
def test_category_fallback(category):
    from news.clinic_ai import clean_diagnosis
    from news.clinic_interview import clean_interview
    item = {'name': 'Amalgamat kategorii', 'category': category, 'quote': 'tekst'}
    expected = 'Fałszywa analogia i skojarzenie'
    result = clean_diagnosis({'verdict': 'spin', 'techniques': [item]}, 'tekst', {})
    assert result['techniques'][0]['category'] == expected
    result = clean_interview({'guest': {'verdict': 'spin', 'techniques': [item]},
                              'host': {'notes': [item]}}, 'tekst', {})
    assert result['guest_analysis']['techniques'][0]['category'] == expected
    assert result['host_analysis']['notes'][0]['category'] == expected


def test_technique_groups_prefer_category():
    from news.techniques import technique_groups
    assert technique_groups([
        {'name': 'Straszenie', 'category': 'Przesada'},
        {'name': 'Straszenie', 'category': 'Inne'},
        {'name': 'Straszenie', 'category': 'Nieznana'},
        {'name': 'Straszenie'}, None,
    ]) == ['Przesada', 'Inne', 'Straszenie']


@pytest.mark.parametrize('category,expected', [('Przesada', 'Przesada'), ('Nieznana', 'Straszenie'), (None, 'Straszenie')])
def test_council_preserves_category_and_descriptive_name(category, expected):
    from news.clinic_council import combine
    item = {'id': 'straszenie', 'name': 'Straszenie katastrofą', 'quote': 'cytat', 'explanation': 'opis'}
    if category is not None:
        item['category'] = category
    result = combine([{'verdict': 'spin', 'intensity': 70, 'techniques': [item]}])
    assert result['techniques'][0]['category'] == expected
    assert result['techniques'][0]['name'] == item['name']


@pytest.mark.django_db
def test_category_save_and_backfill():
    from io import StringIO
    from django.core.management import call_command
    from news.clinic_models import ClinicInterview

    items = [{'name': 'Straszenie', 'category': 'Nieznana', 'quote': 'cytat', 'extra': 7},
             {'name': 'Nowa technika'}, {'name': 'Straszenie', 'category': 'Przesada'}]
    row = diagnosis(account(), 999, techniques=items)
    row.refresh_from_db()
    assert [item['category'] for item in row.techniques] == ['Straszenie', 'Inne', 'Przesada']
    interview = ClinicInterview.objects.create(day=timezone.localdate(), video_id='abcdefghijk',
                                               guest_analysis={'techniques': items}, host_analysis={'notes': items})
    interview.refresh_from_db()
    assert interview.guest_analysis['techniques'][0]['category'] == 'Straszenie'
    assert interview.host_analysis['notes'][0]['category'] == 'Straszenie'
    # QuerySet.update odtwarza stare dane z pominięciem walidacji modelu.
    SpinDiagnosis.objects.filter(pk=row.pk).update(techniques=items)
    ClinicInterview.objects.filter(pk=interview.pk).update(guest_analysis={'techniques': items, 'summary': 'opis'})
    before = SpinDiagnosis.objects.values().get(pk=row.pk)
    interview_before = ClinicInterview.objects.values().get(pk=interview.pk)
    output = StringIO()
    call_command('backfill_technique_categories', dry_run=True, stdout=output)
    assert SpinDiagnosis.objects.values().get(pk=row.pk) == before
    assert ClinicInterview.objects.values().get(pk=interview.pk) == interview_before
    assert 'Nowa technika' in output.getvalue() and 'DRY RUN' in output.getvalue()
    call_command('backfill_technique_categories', stdout=StringIO())
    after = SpinDiagnosis.objects.values().get(pk=row.pk)
    expected = [{**item, 'category': category} for item, category in zip(items, ['Straszenie', 'Inne', 'Przesada'])]
    assert after == {**before, 'techniques': expected}
    assert ClinicInterview.objects.values().get(pk=interview.pk) == {
        **interview_before, 'guest_analysis': {'techniques': expected, 'summary': 'opis'}}
    output = StringIO()
    call_command('backfill_technique_categories', stdout=output)
    assert '0 diagnoz' in output.getvalue()


@pytest.mark.django_db
def test_domestic_party():
    figure = PublicFigure.objects.create(canonical_name='Anna Test', role_category='european',
                                        role_title='Europosłanka', political_alignment='PPE')
    assert clinic.party_data(figure) is None
    role = PublicFigureRole.objects.create(public_figure=figure, role_category='european',
                                          role_title='Europosłanka', party='🍀 PSL')
    assert clinic.party_data(figure)['short'] == 'PSL'
    assert clinic.party_affiliation(figure)['eu_group'] == 'PPE'
    role.archived = True
    role.save()
    assert clinic.party_data(figure) is None
    assert clinic.clean_account_name('🇵🇱 🍀 PSL ❤️') == 'PSL'


@pytest.mark.django_db
@pytest.mark.parametrize('eu_group', ['PfE', 'PPE', 'ECR'])
def test_roster_group_and_verified_account(eu_group):
    acc = account()
    roster = ParliamentaryRosterEntry.objects.create(source='ep', external_id='1', full_name='Anna Test', club=eu_group)
    figure = PublicFigure.objects.create(canonical_name='Anna Test', role_category='european',
                                        role_title='Europosłanka', political_alignment='PiS',
                                        parliamentary_roster_entry=roster)
    candidate = PoliticalAccountCandidate.objects.create(handle=acc.handle, display_name='Anna Test',
                                                         classification='politician', resolved_account=acc)
    SocialHandleEvidence.objects.create(subject_content_type=ContentType.objects.get_for_model(PublicFigure),
                                        subject_object_id=figure.pk, handle=acc.handle,
                                        candidate=candidate, status='candidate_created')
    diagnosis(acc, 999)
    data = APIClient().get('/api/clinic/spins/', {'party': 'PiS'}).json()
    assert data['count'] == 1
    assert data['results'][0]['author']['party']['code'] == 'PiS'
    assert data['results'][0]['author']['eu_group'] == eu_group
    assert stats_data()['by_party']['PiS']['diagnosed'] == 1


def diagnosis(acc, number, **kwargs):
    defaults = dict(status='approved', verdict='spin', intensity=60,
                    diagnosed_at=timezone.now(), headline='Podatki', summary='Opis',
                    techniques=[{'name': 'Liczby bez punktu odniesienia'},
                                {'name': 'Liczba bez punktu odniesienia'}])
    defaults.update(kwargs)
    return SpinDiagnosis.objects.create(post=post(acc, str(number)), **defaults)


@pytest.mark.django_db
def test_statistics(monkeypatch):
    acc = account()
    other = account('government', 'other', '102')
    for index, verdict in enumerate(['spin', 'partial', 'no_spin', 'unclear']):
        diagnosis(acc, 100 + index, verdict=verdict, intensity=index * 20)
    diagnosis(other, 200, intensity=100)
    diagnosis(acc, 201, hidden_at=timezone.now())
    unavailable = diagnosis(acc, 202)
    unavailable.post.available = False
    unavailable.post.save()
    diagnosis(acc, 203, status='pending_review')
    diagnosis(acc, 204, diagnosed_at=timezone.now() - timedelta(days=40))
    data = APIClient().get('/api/clinic/stats/').json()
    assert data['totals']['diagnosed']['total'] == 6
    assert data['by_camp']['opposition']['diagnosed'] == 4
    assert data['by_camp']['opposition']['average_intensity'] == 30
    assert data['by_camp']['opposition']['enough_data'] is False
    assert data['by_camp']['opposition']['intensity_histogram'][1]['count'] == 1
    assert data['by_camp']['government']['intensity_histogram'][4]['count'] == 1
    assert data['techniques']['Liczba bez punktu odniesienia']['opposition']['count'] == 4
    assert data['by_party']['unknown']['diagnosed'] == 5
    assert data['by_party']['unknown']['camp'] == 'mixed'
    assert data['accounts'][0]['diagnosed'] == 4
    assert len(data['daily']) == 30
    assert sum(day['by_camp']['opposition']['diagnosed'] for day in data['daily']) == 4
    assert sum(day['by_camp']['opposition']['spins'] for day in data['daily']) == 2
    assert cache.get(CACHE_KEY) is not None
    monkeypatch.setattr(clinic, 'published_diagnoses', lambda: pytest.fail('Pominięto cache'))
    assert stats_data()['by_camp'] == data['by_camp']


@pytest.mark.django_db
def test_dates_visibility_and_funnel():
    acc = account()
    start = clinic.local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    first = diagnosis(acc, 801, diagnosed_at=start)
    first.post.published_at = start
    first.post.save()
    last = diagnosis(acc, 802)
    last.post.published_at = start + timedelta(days=1) - timedelta(microseconds=1)
    last.post.save()
    tomorrow = diagnosis(acc, 803)
    tomorrow.post.published_at = start + timedelta(days=1)
    tomorrow.post.save()
    diagnosis(acc, 804, status='flagged', diagnosed_at=None, verdict='')
    diagnosis(acc, 805, status='queued', diagnosed_at=None, verdict='')
    diagnosis(acc, 806, hidden_at=timezone.now())
    data = APIClient().get('/api/clinic/spins/', {'date_from': start.date().isoformat(),
                                               'date_to': start.date().isoformat()}).json()
    assert data['count'] == 2
    assert {row['id'] for row in data['results']} == {first.pk, last.pk}
    assert stats_data()['funnel']['flagged_queued']['count'] == 2


@pytest.mark.django_db
def test_min_sample():
    acc = account()
    for index in range(10):
        diagnosis(acc, 300 + index)
    data = stats_data()
    assert data['by_camp']['opposition']['enough_data'] is True
    assert data['accounts'][0]['enough_data'] is True
    assert data['techniques']['Liczba bez punktu odniesienia']['opposition']['enough_data'] is True


@pytest.mark.django_db
def test_filters_and_legacy(monkeypatch):
    acc = account()
    figure = PublicFigure.objects.create(canonical_name='Anna Żółć', role_category='european',
                                        role_title='Europosłanka', political_alignment='PiS')
    monkeypatch.setattr(clinic, 'figures_by_account', lambda ids: {acc.pk: figure})
    rows = [diagnosis(acc, 400 + index, intensity=index) for index in range(23)]
    client = APIClient()
    old = client.get('/api/clinic/spins/').json()
    assert old['count'] == 23 and len(old['results']) == 20 and old['next_page'] == 2
    assert old['results'][0]['id'] == rows[-1].pk
    assert old['results'][0]['technique_names'] == ['Liczby bez punktu odniesienia', 'Liczba bez punktu odniesienia']
    assert old['results'][0]['technique_groups'] == ['Liczba bez punktu odniesienia']
    assert client.get('/api/clinic/spins/', {'page': 2}).json()['next_page'] is None
    for query in ('Podatki', 'Opis', 'żółć', acc.handle):
        assert client.get('/api/clinic/spins/', {'q': query}).json()['count'] == 23
    params = {'party': 'PiS', 'technique': 'Liczba bez punktu odniesienia', 'intensity_min': 10,
              'intensity_max': 20, 'sort': 'strong', 'camp': 'opposition', 'verdict': 'spin',
              'date_from': timezone.localdate(rows[0].post.published_at).isoformat(),
              'date_to': timezone.localdate(rows[0].post.published_at).isoformat()}
    filtered = client.get('/api/clinic/spins/', params).json()
    assert filtered['count'] == 11 and filtered['results'][0]['intensity'] == 20
    assert client.get('/api/clinic/spins/', {'party': 'PSL'}).json()['count'] == 0
    assert client.get('/api/clinic/spins/', {'q': 'brak wyników'}).json()['count'] == 0
    rows[0].refresh_from_db()
    assert rows[0].techniques[0]['name'] == 'Liczby bez punktu odniesienia'


@pytest.mark.django_db
@pytest.mark.parametrize('params', [{'intensity_min': '-1'}, {'intensity_max': '101'},
    {'intensity_min': '20', 'intensity_max': '10'}, {'date_from': 'x'},
    {'date_from': '2026-09-29', 'date_to': '2026-09-28'}, {'sort': 'x'}, {'technique': 'x'}])
def test_invalid_filters(params):
    assert APIClient().get('/api/clinic/spins/', params).status_code == 400


@pytest.mark.django_db
def test_cards_keep_all_technique_types_for_the_shared_presentation_model():
    items = [{'name': f'Example {index}', 'category': category}
             for index, category in enumerate(CANONICAL_TECHNIQUES[:7])]
    row = diagnosis(account(), 9901, techniques=items)
    card = APIClient().get('/api/clinic/spins/').json()['results'][0]
    assert len(card['technique_names']) == 4  # legacy preview remains compatible
    assert card['technique_types'] == [{'name': item['name'], 'category': item['category']}
                                      for item in row.techniques]
    assert len(card['technique_types']) == 7


@pytest.mark.django_db
def test_account_filter_exact_id_combines_filters_and_paginates():
    acc = account()
    other = account('opposition', 'posel_test_extra', '102')
    rows = [diagnosis(acc, 2000 + index, intensity=20 + index) for index in range(21)]
    diagnosis(other, 3000, headline='posel_test', summary='Ten sam autor w tekście')
    diagnosis(acc, 3001, hidden_at=timezone.now())
    diagnosis(acc, 3002, status='pending_review')
    unavailable = diagnosis(acc, 3003)
    unavailable.post.available = False
    unavailable.post.save()
    client = APIClient()
    result = client.get('/api/clinic/spins/', {'account': acc.pk}).json()
    assert result['count'] == 21 and result['next_page'] == 2
    assert all(row['author']['account_id'] == acc.pk for row in result['results'])
    last = client.get('/api/clinic/spins/', {'account': acc.pk, 'page': 2}).json()
    assert [row['id'] for row in last['results']] == [rows[0].pk]
    assert last['next_page'] is None
    combined = client.get('/api/clinic/spins/', {'account': acc.pk, 'intensity_min': 40, 'sort': 'strong'}).json()
    assert [row['id'] for row in combined['results']] == [rows[-1].pk]
    assert client.get('/api/clinic/spins/', {'account': acc.pk, 'camp': 'government'}).json()['count'] == 0
    assert client.get('/api/clinic/spins/', {'account': 99999999}).json()['count'] == 0


@pytest.mark.django_db
@pytest.mark.parametrize('account_id', ['posel_test', '-1', '0', '1.5', '1e2', '9223372036854775808', '9' * 100])
def test_account_filter_invalid_id(account_id):
    assert APIClient().get('/api/clinic/spins/', {'account': account_id}).status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize('first', ['read', 'diagnosis'])
def test_period_uses_first_collection_or_diagnosis_and_caches_timestamp(first):
    from django.utils.dateparse import parse_datetime
    acc = account()
    row = diagnosis(acc, 9000)
    early = timezone.now() - timedelta(days=60)
    later = early + timedelta(days=1)
    type(row.post).objects.filter(pk=row.post_id).update(
        fetched_at=early if first == 'read' else later,
        published_at=early - timedelta(days=100))  # data źródła nie jest datą startu Kliniki
    SpinDiagnosis.objects.filter(pk=row.pk).update(diagnosed_at=early if first == 'diagnosis' else later)
    before = timezone.now()
    client = APIClient()
    for endpoint in ('/api/clinic/', '/api/clinic/stats/'):
        value = client.get(endpoint).json()
        assert value['since'] == timezone.localdate(early).isoformat()
        assert before <= parse_datetime(value['generated_at']) <= timezone.now()
        again = client.get(endpoint).json()
        assert again['generated_at'] == value['generated_at']


@pytest.mark.django_db
def test_empty_period_and_hidden_diagnoses():
    client = APIClient()
    for endpoint in ('/api/clinic/', '/api/clinic/stats/'):
        value = client.get(endpoint).json()
        assert value['since'] is None and value['generated_at']
    cache.clear()
    row = diagnosis(account(), 9001, hidden_at=timezone.now(), diagnosed_at=timezone.now() - timedelta(days=60))
    expected = timezone.localdate(row.post.fetched_at).isoformat()
    assert client.get('/api/clinic/').json()['since'] == expected
    assert client.get('/api/clinic/stats/').json()['since'] == expected


@pytest.mark.django_db
def test_report_categories_count_once_per_diagnosis_and_keep_original_names():
    from news.weekly_report import build
    acc = account()
    diagnosis(acc, 9100, techniques=[
        {'name': 'Liczby bez kontekstu', 'category': 'Liczba bez punktu odniesienia'},
        {'name': 'Kwota bez porównania', 'category': 'Liczba bez punktu odniesienia'},
        {'name': 'Dawna technika', 'category': 'Inne'},
    ])
    diagnosis(acc, 9101, techniques=[{'name': 'Liczby bez kontekstu', 'category': 'Liczba bez punktu odniesienia'}])
    value = build()['techniques']['opposition']
    assert len(value) == 2
    assert value[0]['category'] == 'Liczba bez punktu odniesienia' and value[0]['count'] == 2
    assert value[0]['original_names'] == ['Kwota bez porównania', 'Liczby bez kontekstu']
    assert value[1]['category'] == 'Inne' and value[1]['count'] == 1
