"""przeszłość.today bez cen i z wszystkimi funkcjami w becie (właściciel 7.10)."""
from datetime import timedelta
from pathlib import Path
import json
import re

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from news import przeszlosc_dostep as dostep
from news.political_models import ParliamentaryRosterEntry, PublicFigure
from news.sales_models import SalesLead

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[2]
# Cena: liczba z walutą albo okresem rozliczenia, słowo „cennik”, nazwy planów z ceną. Kwoty z danych (dotacje,
# kilometrówki) są formatowane w kodzie zmienną, nigdy liczbą wpisaną na sztywno.
PRICE = re.compile(r'\d[\d\s.,]*\s?(zł|pln|eur\b|€)|/\s?mies|cennik|cena\s*/|plan (pro|zespół)|\bnetto\b', re.I)


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    cache.clear()
    yield
    cache.clear()


def figure():
    entry = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='5', full_name='Anna Testowa', term=10,
                                                    source_url='https://api.sejm.gov.pl/sejm/term10/MP')
    return PublicFigure.objects.create(canonical_name='Anna Testowa', role_category='parliamentary', role_title='Posłanka',
                                       evidence_url='https://sejm.gov.pl', parliamentary_roster_entry=entry)


def test_features_api_lists_everything_open_with_beta_label_and_no_prices():
    data = APIClient().get('/api/przeszlosc/funkcje/').json()
    assert data['beta'] is True and data['label'] == 'Beta - wszystkie funkcje bezpłatnie' and data['locked'] == []
    assert len(data['features']) == len(dostep.FEATURES) >= 15 and all(f['open'] for f in data['features'])
    assert {f['id'] for f in data['features']} >= {'alerty', 'eksport', 'mianowniki', 'krs', 'pieniadze', 'odstepstwa'}
    assert not PRICE.search(json.dumps(data, ensure_ascii=False))
    for f in data['features']:
        assert len(f['title']) <= 32, f['title']  # tytuł w jednej linii boksu
        assert f['href'].startswith(('/przeszlosc', 'https://spin.clinic'))


def test_beta_opens_every_pro_feature_for_anonymous_visitor():
    me = figure()
    client = APIClient()
    person = client.get(f'/api/przeszlosc/osoba/{me.pk}/').json()
    assert person['access'] == {'beta': True, 'label': dostep.BETA_LABEL, 'locked': []}
    assert person['denominators'] is not None
    assert client.get(f'/api/przeszlosc/osoba/{me.pk}/?eksport=csv').status_code == 200
    assert client.get('/api/przeszlosc/odstepstwa/').status_code != 403
    topic = client.get('/api/przeszlosc/temat/?q=CPK').json()
    assert 'eu_funds' in topic and topic['access']['beta'] is True
    assert client.get('/api/przeszlosc/start/').json()['access']['label'] == dostep.BETA_LABEL


@override_settings(PRZESZLOSC_BETA_ALL_FEATURES=False)
def test_paid_plan_code_stays_behind_the_flag():
    me = figure()
    client = APIClient()
    person = client.get(f'/api/przeszlosc/osoba/{me.pk}/').json()
    assert person['access']['beta'] is False and person['access']['label'] == ''
    assert set(person['access']['locked']) == dostep.PRO
    assert person['denominators'] is None and person['organisations'] == []
    blocked = client.get(f'/api/przeszlosc/osoba/{me.pk}/?eksport=csv')
    assert blocked.status_code == 403 and blocked.json()['feature'] == 'export'
    assert not PRICE.search(blocked.json()['detail'])
    assert client.get('/api/przeszlosc/odstepstwa/').status_code == 403
    assert 'eu_funds' not in client.get('/api/przeszlosc/temat/?q=CPK').json()
    alert = client.post('/api/przeszlosc/alerty/', {'email': 'ktos@example.org', 'consent': True, 'kind': 'topic', 'q': 'CPK'},
                        format='json')
    assert alert.status_code == 403
    # pilot (adres z przyznanym pilotem) i personel mają Pro także bez bety
    SalesLead.objects.create(kind='pilot', name='Pilot', email='pilot@example.org', token='t' * 40, consent_version='x',
                             status='confirmed', pilot_until=timezone.localdate() + timedelta(days=30))
    assert dostep.has('alerts', email='pilot@example.org') and not dostep.has('alerts', email='ktos@example.org')
    staff = get_user_model().objects.create_user('redaktor', 'r@example.org', 'x', is_staff=True)
    client.force_authenticate(staff)
    assert client.get(f'/api/przeszlosc/osoba/{me.pk}/?eksport=csv').status_code == 200
    assert client.get('/api/przeszlosc/funkcje/').json()['locked'] == []


def test_no_prices_on_przeszlosc_pages_and_in_backend_texts():
    files = list((ROOT / 'frontend-spin' / 'app' / 'przeszlosc').rglob('*.tsx'))
    files += [ROOT / 'backend' / 'news' / name for name in ('przeszlosc.py', 'przeszlosc_osoba.py', 'przeszlosc_alerts.py',
                                                            'przeszlosc_dostep.py', 'sales.py')]
    assert len(files) > 8
    for path in files:
        text = path.read_text(encoding='utf-8')
        strings = re.findall(r"'[^'\n]*'|\"[^\"\n]*\"|>[^<>{}\n]+<", text)  # tylko teksty, nie kod formatujący kwoty z danych
        hits = [s for s in strings if PRICE.search(s)]
        assert not hits, (path.name, hits[:3])
