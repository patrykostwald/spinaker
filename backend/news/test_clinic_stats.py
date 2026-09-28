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
