"""Głosowania według rodzaju (dopisek 23.10): liczniki rodzajów, opis braków, filtry wyniku i zgodności z klubem."""
from datetime import date

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from news import przeszlosc_glosowania_rodzaje as gr
from news.models import Article, Ballot, ParliamentaryVoting, Source
from news.political_models import PublicFigure, PublicFigureRole
from news.public_records_models import PublicRecord, PublicRecordPerson

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _cache():
    cache.clear()
    yield
    cache.clear()


def world():
    me = PublicFigure.objects.create(canonical_name='Anna Kowalska', role_category='parliamentary', role_title='Posłanka',
                                     evidence_url='https://sejm.gov.pl')
    PublicFigureRole.objects.create(public_figure=me, role_category='parliamentary', role_title='Posłanka X kadencji',
                                    evidence_url='https://sejm.gov.pl', import_key='sejm-term:10:1', since=date(2023, 11, 13), party='KO')
    source = Source.objects.create(name='Sejm', url='https://sejm.example')
    for number, day, counts, votes in (
        (1, '2026-03-01T10:00:00Z', {'yes': 3, 'majorityVotes': 2}, ['YES', 'YES', 'NO']),   # przyjęte, z klubem
        (2, '2026-04-01T10:00:00Z', {'yes': 1, 'majorityVotes': 2}, ['NO', 'YES', 'YES']),   # odrzucone, inaczej niż klub
    ):
        article = Article.objects.create(source=source, title=f'Głosowanie {number}', url=f'https://sejm.example/{number}', published_date=day)
        voting = ParliamentaryVoting.objects.create(article=article, term=10, sitting=40, number=number, motion='całość', kind='ELECTRONIC', counts=counts)
        for mp_id, vote in enumerate(votes, start=1):
            Ballot.objects.create(voting=voting, mp_id=mp_id, name=f'P{mp_id}', club='KO', vote=vote)
    ep = PublicRecord.objects.create(source='howtheyvote', kind='ep_vote', external_id='e1', title='Rezolucja PE', date=date(2026, 2, 2),
                                     source_url='https://howtheyvote.eu/votes/1', response_url='https://howtheyvote.eu/', response_sha256='0',
                                     data={'result': 'ADOPTED', 'polish': {'FOR': 1}, 'votes': [{'ep_id': 9, 'position': 'FOR', 'group': 'EPP'}]})
    PublicRecordPerson.objects.create(record=ep, term=0, mp_id=9, figure=me)
    return me


def test_kinds_counts_and_missing_notes():
    me = world()
    data = gr.person_payload(me, gr.params({}))
    kinds = {k['key']: k for k in data['kinds']}
    assert kinds['sejm']['count'] == 2 and kinds['pe']['count'] == 1
    assert kinds['komisje']['count'] == 0 and 'Brak danych w źródle' in kinds['komisje']['note']
    assert kinds['senat']['count'] == 0 and kinds['senat']['note']
    assert data['terms'] == [10] and data['count'] == 2


def test_filters_outcome_and_club():
    me = world()
    against = gr.person_payload(me, gr.params({'zgodnosc': 'inaczej'}))
    assert [r['title'] for r in against['results']] == ['Głosowanie 2'] and against['results'][0]['with_club'] is False
    assert gr.person_payload(me, gr.params({'wynik': 'przyjete'}))['results'][0]['title'] == 'Głosowanie 1'
    assert gr.person_payload(me, gr.params({'od': '2026-03-15'}))['count'] == 1
    pe = gr.person_payload(me, gr.params({'rodzaj': 'pe'}))
    assert pe['results'][0]['vote'] == 'za' and pe['results'][0]['outcome'] == 'przyjete' and not pe['club_filter']
    for bad in ({'rodzaj': 'x'}, {'wynik': 'x'}, {'zgodnosc': 'x'}, {'od': '2026-13-01'}, {'kadencja': 'x'}):
        with pytest.raises(ValueError):
            gr.params(bad)


def test_endpoints(monkeypatch, settings):
    me = world()
    client = APIClient()
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    settings.PRZESZLOSC_VOTES_LIST_ENABLED = True
    body = client.get(f'/api/przeszlosc/osoba/{me.pk}/glosowania/?rodzaj=sejm').json()
    assert body['count'] == 2
    assert client.get(f'/api/przeszlosc/osoba/{me.pk}/glosowania/?rodzaj=x').status_code == 400
    general = client.get('/api/przeszlosc/glosowania/?rodzaj=pe').json()
    assert general['total'] == 1 and general['filter']['rodzaj'] == 'pe' and {k['key'] for k in general['kinds']} == set(gr.KINDS)
    assert client.get('/api/przeszlosc/glosowania/?rodzaj=senat').json()['total'] == 0
    assert client.get('/api/przeszlosc/glosowania/').json()['filter']['rodzaj'] == 'sejm'


def test_ep_page_filters_result_and_pages():
    world()
    page = gr.ep_page({'wynik': 'przyjete'}, 10)
    assert page['count'] == 1 and page['results'][0]['outcome'] == 'przyjete' and page['results'][0]['polish']
    assert gr.ep_page({'wynik': 'odrzucone'}, 10)['count'] == 0
