import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from news.feedback import clean_path
from news.feedback_models import BugReport, JourneyStep

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fresh_throttle():
    cache.clear()


def test_clean_path_hides_ids_and_people():
    assert clean_path('/spinki/49?x=1#a') == '/spinki/:id'
    assert clean_path('/profile/jan.kowalski/spinki') == '/profile/:nick/spinki'
    assert clean_path('/klinika/12/komentarze/7') == '/klinika/:id/komentarze/:id'
    assert clean_path('https://evil.example/') == ''
    assert clean_path('(wejście)') == '(wejście)'


def test_bug_report_saved_without_secret_fields(monkeypatch):
    sent = []
    monkeypatch.setattr('news.feedback.notify', lambda report: sent.append(report.pk))
    client = APIClient()
    response = client.post('/api/feedback/bug/', {'text': 'Przycisk wróć nie działa', 'path': '/spinki/49?utm=x',
        'viewport': '390x844', 'theme': 'light', 'trail': ['/', '/spinki/49', '/profile/ania']}, format='json')
    assert response.status_code == 201
    report = BugReport.objects.get()
    assert report.path == '/spinki/:id' and report.trail == ['/', '/spinki/:id', '/profile/:nick']
    assert report.user is None and report.status == 'new'


def test_bug_report_validation_and_throttle(monkeypatch):
    monkeypatch.setattr('news.feedback.notify', lambda report: None)
    client = APIClient()
    assert client.post('/api/feedback/bug/', {'text': 'x' * 1300, 'path': '/'}, format='json').status_code == 400
    codes = [client.post('/api/feedback/bug/', {'text': f'Opis błędu {i}', 'path': '/'}, format='json').status_code for i in range(6)]
    assert codes[:4] == [201] * 4 and codes[4] == 429  # nieudana próba też się liczy


def test_journey_counts_only_aggregates():
    client = APIClient()
    steps = [['(wejście)', '/', 'nav'], ['/', '/spinki/49', 'nav'], ['/spinki/49', '/spinki/49', 'click:sc-trop-overlay__side-back'],
             ['/spinki/50', '/spinki/50', 'rage:sc-joint'], ['/spinki/50', '(wyjście)', 'exit'], ['/x', '/y', 'DROP TABLE']]
    for _ in range(2):
        assert client.post('/api/feedback/journey/', {'steps': steps, 'device': 'phone'}, format='json').status_code == 204
    assert JourneyStep.objects.count() == 5
    assert JourneyStep.objects.get(source='/', target='/spinki/:id').count == 2
    assert not JourneyStep.objects.filter(action='DROP TABLE').exists()
    assert client.post('/api/feedback/journey/', {'steps': 'zle', 'device': 'tv'}, format='json').status_code == 204
