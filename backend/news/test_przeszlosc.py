import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from news.political_models import PoliticalAccount, PoliticalPost
from news.przeszlosc import terms, topic_graph

pytestmark = pytest.mark.django_db


def post(key, camp, text):
    account = PoliticalAccount.objects.create(user_id=key, handle=f'konto{key}', display_name=f'Konto {key}', camp=camp)
    return PoliticalPost.objects.create(account=account, post_id=key, url=f'https://x.com/konto{key}/status/{key}', text=text,
                                        published_at=timezone.now(), camp_at_collection=camp)


def test_terms():
    assert terms('CPK, lotnisko; a') == ['CPK', 'lotnisko']
    assert terms('') == []


def test_media_description_limit_and_material_type():
    from news.models import Article, Source
    source = Source.objects.create(name='Redakcja', url='https://media.example')
    Article.objects.bulk_create([
        Article(source=source, title=f'Rozmowa z ekspertem {i}', description='Budowa CPK.',
                url=f'https://media.example/rozmowa/{i}', published_date=timezone.now())
        for i in range(105)
    ])
    data = topic_graph('CPK')
    media = [n for n in data['nodes'] if n['kind'] == 'media']
    assert len(media) == 100
    assert all(n['material_type'] == 'wywiad' and n['kind_label'] == 'wywiad'
               and n['match_type'] == 'automatic' for n in media)
    assert data['edges'] == []  # Dopasowanie tematu nie ustanawia relacji osoby.


def test_duplicate_media_never_leave_dangling_confirmed_edges():
    from news.models import Article, Source
    from news.political_models import PublicFigure, PublicFigureArticleReference
    source = Source.objects.create(name='Redakcja', url='https://media.example')
    person = PublicFigure.objects.create(canonical_name='Anna Kowalska')
    for i in range(2):
        article = Article.objects.create(source=source, title='CPK: aktualności',
                                         url=f'https://media.example/{i}', published_date=timezone.now())
        PublicFigureArticleReference.objects.create(public_figure=person, article=article,
                                                     verification_status='confirmed')
    data = topic_graph('CPK')
    ids = {n['id'] for n in data['nodes']}
    assert len([n for n in data['nodes'] if n['kind'] == 'media']) == 1
    assert all(e['source'] in ids and e['target'] in ids for e in data['edges'])


def test_same_measure_for_both_camps():
    post('1', 'government', 'CPK ruszy w terminie.')
    post('2', 'opposition', 'Rząd opóźnia CPK.')
    post('3', 'opposition', 'Inny temat.')
    data = topic_graph('CPK')
    statements = [n for n in data['nodes'] if n['kind'] == 'statement']
    assert {n['camp'] for n in statements} == {'government', 'opposition'}
    assert data['counts']['statement'] == 2 and len(data['edges']) == 2


def test_endpoint_off_by_default(monkeypatch):
    client = APIClient()
    assert client.get('/api/przeszlosc/temat/?q=CPK').status_code == 404
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    assert client.get('/api/przeszlosc/temat/?q=a').status_code == 400
    assert client.get('/api/przeszlosc/temat/?q=CPK').json()['terms'] == ['CPK']


def test_start_counts_and_latest():
    post('9', 'government', 'CPK ruszy.')
    data = APIClient().get('/api/przeszlosc/start/').json()
    assert data['counts']['posts'] == 1 and data['latest'] == [] and data['topics_enabled'] is False


def test_inflection_and_acronym_expansion():
    post('21', 'government', 'Ceny energii spadną.')
    post('22', 'opposition', 'Budowa Centralnego Portu Komunikacyjnego stoi.')
    assert topic_graph('ceny energia')['counts']['statement'] == 1
    assert topic_graph('CPK')['counts']['statement'] == 1


def test_pick_topics_ranks_richest():
    from news.przeszlosc import auto_topics, pick_topics
    for i in range(4):
        post(str(30 + i), 'government' if i % 2 else 'opposition', 'KPO znowu opóźnione, KPO.')
    rows = pick_topics()
    assert all(r['edges'] >= 3 for r in rows) and auto_topics() == rows


def test_topic_votes_by_club_and_name(monkeypatch):
    from news.models import Article, Ballot, ParliamentaryVoting, Source
    from news.przeszlosc import topic_votes
    source = Source.objects.create(name='Sejm', url='https://sejm.example')
    article = Article.objects.create(source=source, title='Pkt 3. Projekt ustawy o podatku VAT', url='https://sejm.example/v',
                                     published_date='2026-09-20T10:00:00Z')
    voting = ParliamentaryVoting.objects.create(article=article, term=10, sitting=40, number=7, motion='wniosek o odrzucenie',
                                                kind='ELECTRONIC', counts={'yes': 2, 'no': 1})
    for n, (name, club, vote) in enumerate([('Anna A', 'KO', 'YES'), ('Jan B', 'KO', 'YES'), ('Ewa C', 'PiS', 'NO'), ('Piotr D', 'PiS', 'ABSENT')]):
        Ballot.objects.create(voting=voting, mp_id=n + 1, name=name, club=club, vote=vote)
    rows = topic_votes('VAT')
    assert len(rows) == 1 and rows[0]['result'] == {'yes': 2, 'no': 1}
    assert {c['club']: c['votes'] for c in rows[0]['clubs']} == {'KO': {'za': 2}, 'PiS': {'przeciw': 1, 'nieobecny': 1}}
    assert ['Ewa C', 'PiS', 'przeciw'] in rows[0]['members'] and 'NrGlosowania=7' in rows[0]['url']
    assert topic_votes('lotnisko') == []
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    data = APIClient().get('/api/przeszlosc/temat/?q=VAT').json()
    assert data['counts']['vote'] == 1 and data['votes'][0]['id'] == '10/40/7'


def test_topic_rss(settings):
    """Kanał RSS tematu: poprawny XML z elementami tematu, wyłączony razem z przeszłością."""
    from unittest import mock
    from django.test import Client
    from news import przeszlosc
    graph = {'nodes': [{'id': 'post:1', 'kind': 'statement', 'label': 'VAT & akcyza <test>', 'date': '2026-10-03', 'url': 'https://x.com/a/1', 'sub': 'Ktoś'},
                       {'id': 'figure:1', 'kind': 'person', 'label': 'Osoba'}]}
    with mock.patch.object(przeszlosc, 'enabled', return_value=True), mock.patch.object(przeszlosc, 'topic_graph', return_value=graph):
        r = Client().get('/api/przeszlosc/rss/', {'q': 'VAT'})
    assert r.status_code == 200 and r['Content-Type'].startswith('application/rss+xml')
    body = r.content.decode()
    assert '<item>' in body and 'VAT &amp; akcyza &lt;test&gt;' in body and 'Osoba' not in body
    with mock.patch.object(przeszlosc, 'enabled', return_value=False):
        assert Client().get('/api/przeszlosc/rss/', {'q': 'VAT'}).status_code == 404


def test_expand_vat_matches_full_name():
    """Skrót VAT trafia też w pełną nazwę podatku (druki Sejmu piszą ją słownie)."""
    from news.przeszlosc import EXPAND, _match
    assert 'podatek od towarów i usług' in EXPAND['vat']
    q = str(_match(['title'], ['VAT']))
    assert 'podatku od towarów i usług' in q and 'VAT' in q


def test_link_votes_by_official_id(db):
    """Osoba z tematu łączy się z głosowaniem tylko przez oficjalny identyfikator posła."""
    from news.przeszlosc import link_votes
    from news.political_models import ParliamentaryRosterEntry, PublicFigure
    entry = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='77', full_name='Jan Test', term=10, source_url='https://sejm.gov.pl')
    f = PublicFigure.objects.create(canonical_name='Jan Test', role_category='parliamentary', role_title='Poseł', evidence_url='https://sejm.gov.pl',
                                    parliamentary_roster_entry=entry)
    data = {'nodes': [{'id': f'figure:{f.pk}', 'kind': 'person', 'label': 'Jan Test'}], 'edges': [],
            'votes': [{'id': '10/5/3', 'title': 'Ustawa o VAT', 'date': '2026-10-01', 'url': 'https://sejm.gov.pl/g', 'mp_votes': [[77, 'za'], [78, 'przeciw']]}]}
    out = link_votes(data)
    assert {'source': f'figure:{f.pk}', 'target': 'vote:10/5/3', 'label': 'głosował(a): za'} in out['edges']
    assert any(n['id'] == 'vote:10/5/3' for n in out['nodes']) and 'mp_votes' not in out['votes'][0]


def test_krs_w_grafie_tematu_tylko_gdy_podmiot_wystepuje_w_temacie():
    """Śledczy R1, P0-3: funkcje KRS osób, które tylko pojawiły się w temacie, nie wchodzą do grafu."""
    from news.political_models import PublicFigure, PublicFigureOrganisationRelation, RegisteredOrganisation
    from news.public_records_models import PublicRecord, PublicRecordPerson
    record = PublicRecord.objects.create(source='sejm', kind='statement', external_id='k1', title='Sprawa Kołodziejczak',
                                         text='Sprawa Kołodziejczak w Sejmie.', source_url='https://example.org/k1',
                                         response_url='https://example.org/', response_sha256='0')
    names = {'Michał Kołodziejczak': 'Fundacja Agrounia', 'Elżbieta Witek': 'Klub Sportowy Olimpia',
             'Anna Nowak': 'Kołodziejczak Sp. z o.o.'}
    for i, (person_name, org_name) in enumerate(names.items()):
        figure = PublicFigure.objects.create(canonical_name=person_name)
        PublicRecordPerson.objects.create(record=record, figure=figure, term=10, mp_id=100 + i)
        org = RegisteredOrganisation.objects.create(name=org_name, krs_number=f'000000000{i}', kind='company',
                                                    official_register_url='https://ekrs.ms.gov.pl/')
        rel = PublicFigureOrganisationRelation(public_figure=figure, organisation=org, public_role='zarząd',
                                               evidence_url='https://example.org')
        rel.confirm_automatically('krs_register')
        rel.save()
    orgs = {n['label'] for n in topic_graph('Kołodziejczak')['nodes'] if n['kind'] == 'organisation'}
    assert orgs == {'Fundacja Agrounia', 'Kołodziejczak Sp. z o.o.'}
