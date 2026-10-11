import subprocess

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from news import przeszlosc_wersja as pw
from news.feedback_models import BugReport
from news.models import Article, Source
from news.political_models import PublicFigure


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    cache.clear()
    pw._cache.clear()
    for key in (*pw.COMMIT_ENV, *pw.BUILT_ENV):
        monkeypatch.delenv(key, raising=False)
    yield
    pw._cache.clear()


@pytest.mark.django_db
def test_wersja_z_env_i_flagi_bez_sekretow(monkeypatch):
    monkeypatch.setenv('GIT_COMMIT', 'abc1234def5678')
    monkeypatch.setenv('BUILD_TIME', '2026-10-11T08:00:00+02:00')
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    monkeypatch.setenv('SECRET_KEY', 'tajne-nie-pokazuj')
    response = APIClient().get('/api/przeszlosc/wersja/')
    assert response.status_code == 200
    data = response.data
    assert data['commit'] == 'abc1234def5678' and data['commit_short'] == 'abc1234' and data['source'] == 'env'
    assert data['built_at'].startswith('2026-10-11')
    assert data['flags']['przeszlosc_enabled'] is True
    assert 'temat' in data['flags']['features'] and 'open' in data['flags']['features']['alerty']
    assert 'tajne-nie-pokazuj' not in str(response.content)


@pytest.mark.django_db
def test_wersja_z_gita_gdy_brak_env():
    expected = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    data = APIClient().get('/api/przeszlosc/wersja/').data
    assert data['commit'] == expected and data['source'] == 'git'


@pytest.mark.django_db
def test_poprawki_tylko_przyjete_bez_danych_zglaszajacego():
    def report(status, text, **kw):
        return BugReport.objects.create(text=text, path='/przeszlosc', status=status, **kw)
    report('fixed', '[Sprostowanie] osoba:326-donald-tusk\nDonald Tusk\nTajna treść zgłoszenia', contact='a@example.test', staff_note='wewn.')
    report('new', '[Sprostowanie] osoba:1-nowy\nNowy\nczeka')
    report('rejected', '[Sprostowanie] osoba:2-odrzucony\nOdrzucony\nnie')
    report('fixed', 'Zwykły błąd strony, nie sprostowanie')
    response = APIClient().get('/api/przeszlosc/poprawki/')
    assert response.status_code == 200
    assert response.data['count'] == 1
    row = response.data['results'][0]
    assert row['record'] == 'osoba:326-donald-tusk' and row['label'] == 'Donald Tusk'
    assert row['href'] == '/przeszlosc/osoba/326-donald-tusk'
    body = str(response.content)
    assert 'Tajna treść' not in body and 'a@example.test' not in body and 'wewn.' not in body


@pytest.mark.django_db
def test_licznik_artykulow_zgodny_z_wzmiankami(monkeypatch):
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    source = Source.objects.create(name='Redakcja', url='https://example.test')
    figure = PublicFigure.objects.create(canonical_name='Michał Kołodziejczak', role_category='political', role_title='Poseł')
    for i in range(10):
        Article.objects.create(source=source, title=f'Michał Kołodziejczak o rolnictwie {i}', url=f'https://example.test/{i}',
                               published_date=timezone.now())
    data = APIClient().get(f'/api/przeszlosc/osoba/{figure.pk}/').data
    assert len(data['mentions']['results']) == 10
    assert data['materials']['count'] == 0
    assert data['articles_total'] == 10
