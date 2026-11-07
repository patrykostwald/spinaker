import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from news import polls
from news.poll_models import PollVote

pytestmark = pytest.mark.django_db
URL = '/api/polls/udostepnianie-x/'
A, B = 'a' * 32, 'b' * 32


@pytest.fixture(autouse=True)
def clean():
    cache.clear()
    yield
    cache.clear()


def vote(client, voter, question, option, ip='1.1.1.1'):
    return client.post(URL + 'vote/', {'voter': voter, 'question': question, 'option': option}, format='json', REMOTE_ADDR=ip)


def test_one_vote_per_question_can_change():
    c = APIClient()
    assert vote(c, A, 'x', 'p01').status_code == 200
    r = vote(c, A, 'x', 'p06')
    assert r.data['counts']['x']['p01'] == 0 and r.data['counts']['x']['p06'] == 1 and r.data['mine'] == {'x': 'p06'}
    vote(c, A, 'card', 'big')
    assert PollVote.objects.count() == 1 and c.get(URL + '?voter=' + A).data['mine'] == {'x': 'p06', 'card': 'big'}


def test_invalid_votes_rejected():
    c = APIClient()
    assert vote(c, 'zly', 'x', 'p01').status_code == 400
    assert vote(c, A, 'x', 'p99').status_code == 400
    assert vote(c, A, 'nie', 'p01').status_code == 400
    assert c.post('/api/polls/inne/vote/', {}, format='json').status_code == 404


def test_network_limit_and_no_raw_ip_stored(monkeypatch):
    monkeypatch.setattr(polls, 'MAX_PER_NETWORK', 1)
    c = APIClient()
    assert vote(c, A, 'x', 'p01').status_code == 200
    assert vote(c, B, 'x', 'p01').status_code == 429
    assert vote(c, B, 'x', 'p01', ip='2.2.2.2').status_code == 200
    assert not PollVote.objects.filter(network__contains='1.1.1.1').exists()


def test_results_are_public_without_voter():
    c = APIClient()
    vote(c, A, 'hook', 'score')
    r = c.get(URL)
    assert r.status_code == 200 and r.data['voters'] == 1 and r.data['mine'] == {}
