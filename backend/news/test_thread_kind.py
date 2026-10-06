"""Rodzaj spinki (właściciel 6.10): pole kind, wybór czytelnika w kreatorze, rodzaje Dr. Spina z pochodzenia."""
import importlib

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from news.account_models import PersonalContextThread
from news.models import Article, Source
from news.test_diagnosis_threads import diagnosis, offline  # noqa: F401 - fixture bez HTTP i AI

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures('auto_approve_threads')]


@pytest.fixture(autouse=True)
def thread_flags(settings):
    settings.ACCOUNTS_ENABLED = True
    settings.THREADS_ENABLED = True


@pytest.fixture
def owner():
    return get_user_model().objects.create_user(username='autorka')


@pytest.fixture
def article():
    source = Source.objects.create(name='Publisher', url='https://example.org', is_active=True)
    return Article.objects.create(source=source, title='First', url='https://example.org/first', tags=['zdrowie'])


def test_reader_picks_kind_and_default_is_kontekst(owner, article):
    client = APIClient()
    client.force_authenticate(owner)
    url = '/api/account/context-threads/'
    created = client.post(url, {'title': 'Bez rodzaju', 'article_ids': [article.pk]}, format='json')
    assert created.status_code == 201 and created.data['kind'] == 'kontekst'
    picked = client.post(url, {'title': 'Sprzeczność', 'kind': 'sprzecznosc', 'article_ids': [article.pk]}, format='json')
    assert picked.status_code == 201 and picked.data['kind'] == 'sprzecznosc'
    # rodzaj można zmienić przed publikacją
    changed = client.patch(f"{url}{picked.data['id']}/", {'kind': 'pytanie'}, format='json')
    assert changed.status_code == 200 and PersonalContextThread.objects.get(pk=picked.data['id']).kind == 'pytanie'


@pytest.mark.parametrize('kind', ['diagnoza', 'sygnal_lobbingu', 'nieznany', ''])
def test_reader_cannot_use_reserved_or_unknown_kind(owner, article, kind):
    client = APIClient()
    client.force_authenticate(owner)
    response = client.post('/api/account/context-threads/', {'title': 'X', 'kind': kind, 'article_ids': [article.pk]}, format='json')
    assert response.status_code == 400 and 'kind' in response.data


def test_model_forces_kind_from_origin(owner):
    # czytelnik nie dostanie rodzaju Dr. Spina nawet z pominięciem API
    thread = PersonalContextThread.objects.create(owner=owner, title='T', kind='diagnoza')
    assert thread.kind == 'kontekst'
    signal = PersonalContextThread.objects.create(title='Sygnał lobbingu: druk 12', signal_kind='lobbying', signal_key='k1')
    assert signal.kind == 'sygnal_lobbingu'
    narrative = PersonalContextThread.objects.create(title='Nowa narracja: x', signal_kind='new_narrative', signal_key='k2')
    assert narrative.kind == 'nowa_narracja'


def test_diagnosis_thread_is_diagnoza_in_public_api():
    row = diagnosis()
    thread = row.context_thread
    assert thread.kind == 'diagnoza'
    data = APIClient().get(f'/api/community/threads/{thread.pk}/').data
    assert data['kind'] == 'diagnoza' and data['kind_label'] == 'Diagnoza'
    listed = APIClient().get('/api/community/threads/').data['results']
    assert listed[0]['kind'] == 'diagnoza'


def test_migration_fills_kind_from_origin(owner):
    thread = PersonalContextThread.objects.create(title='Lobbing', signal_kind='lobbying', signal_key='k3')
    PersonalContextThread.objects.filter(pk=thread.pk).update(kind='kontekst')
    reader = PersonalContextThread.objects.create(owner=owner, title='Mój')
    from django.apps import apps
    importlib.import_module('news.migrations.0152_thread_kind').fill(apps, None)
    thread.refresh_from_db(); reader.refresh_from_db()
    assert thread.kind == 'sygnal_lobbingu' and reader.kind == 'kontekst'
