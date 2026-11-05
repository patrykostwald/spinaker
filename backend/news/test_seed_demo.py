from io import StringIO

import pytest
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.test import APIClient

from news.clinic_models import ClinicDailyMessage, ClinicInterview, CouncilSeat, SpinDiagnosis, WeeklyReport
from news.management.commands import _seed_demo_content as content
from news.models import Article, Ballot, Source, Thread
from news.newsletter_models import NewsletterSubscriber
from news.political_models import PoliticalPost, PublicFigure

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fresh_cache():
    cache.clear()


def seed():
    call_command('seed_demo', stdout=StringIO())


def counts():
    return {model.__name__: model.objects.count() for model in (
        Source, Article, Thread, Ballot, PublicFigure, PoliticalPost, SpinDiagnosis, ClinicDailyMessage, ClinicInterview,
        CouncilSeat, WeeklyReport, NewsletterSubscriber)}


def test_seed_is_idempotent_and_meets_minimums():
    seed()
    first = counts()
    assert first['Source'] >= 12 and first['Article'] >= 25 and first['Thread'] >= 6
    assert first['PublicFigure'] >= 10 and first['ClinicDailyMessage'] >= 10 and first['ClinicInterview'] >= 4
    assert first['WeeklyReport'] >= 2 and first['NewsletterSubscriber'] >= 3 and first['CouncilSeat'] >= 8
    assert SpinDiagnosis.objects.filter(status='approved').count() >= 8
    seed()
    assert counts() == first


def test_seed_quotes_come_from_post_text():
    # Cytaty technik w diagnozach muszą być dosłownymi fragmentami wpisu (jak w prawdziwym potoku).
    for row in content.DIAGNOSES:
        assert all(quote in row[4] for _, quote, _ in row[10])


def test_seeded_public_endpoints_return_data():
    seed()
    client = APIClient()
    page = client.get('/api/clinic/').data
    assert page['spin_by_camp']['spins']['government'] and page['spin_by_camp']['spins']['opposition']
    assert page['columns']['government'] and page['columns']['opposition'] and page['interview']
    assert client.get('/api/clinic/spins/').data['count'] >= 20
    assert client.get('/api/clinic/messages/').data['count'] >= 10
    assert client.get('/api/clinic/interviews/').data['count'] >= 4
    assert client.get('/api/clinic/report/').data['report']['summary']
    assert len(client.get('/api/clinic/council/').data['members']) >= 8
    stats = client.get('/api/clinic/stats/').data
    assert stats['by_camp']['government']['enough_data'] and stats['by_camp']['opposition']['enough_data']
    assert client.get('/api/public-figures/').data['count'] >= 10
    assert client.get('/api/portal/config/').data['editorial']['government']
    assert client.get('/api/sources/coverage/').data['sources']
    assert client.get('/api/feed/').data['total'] >= 25
    figure = PublicFigure.objects.get(import_key='demo:kwolinska')
    detail = client.get(f'/api/public-figures/{figure.pk}/').data
    assert detail['party']['short'] == 'KO' and detail['x_account'] and detail['votes']['results']
