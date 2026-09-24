import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from news.models import Source, Article, ParliamentaryVoting, Ballot

@pytest.fixture
def votes(db):
    cache.clear()
    source = Source.objects.create(name='Sejm', url='https://api.sejm.gov.pl', source_type='institution')
    def create(number, name, title='Głosowanie nad wetem', motion='Ustawa kryptowalutowa'):
        article = Article.objects.create(source=source, title=title, url=f'https://api.sejm.gov.pl/votes/{number}', category='voting', published_date=timezone.now())
        vote = ParliamentaryVoting.objects.create(article=article,term=10,sitting=1,number=number,motion=motion,kind='electronic',counts={'yes':200,'no':201})
        Ballot.objects.create(voting=vote,mp_id=1,name=name,vote='NO',club='Test')
        Ballot.objects.create(voting=vote,mp_id=2,name='Jan Kowalski',vote='YES',club='Inny')
        return article
    return create

def test_polish_voting_question_returns_official_ballot(votes):
    wanted=votes(1,'Mariusz Gosek')
    votes(2,'Inny Poseł')
    response=APIClient().get('/api/search/',{'q':'Jak głosował poseł Gosek?'})
    assert response.status_code == 200
    result=response.json()
    assert result['query_intent']=='member_votes'
    assert result['total']==1
    direct=result['direct_results'][0]
    assert direct['id']==wanted.pk
    assert direct['url']==wanted.url
    assert direct['voting']['counts']=={'yes':200,'no':201}
    assert [(b['name'],b['vote']) for b in direct['voting']['matching_ballots']]==[('Mariusz Gosek','NO')]

def test_voting_question_keeps_topic_and_matches_same_person(votes):
    wanted=votes(1,'Mariusz Gosek')
    votes(2,'Mariusz Gosek',motion='Budżet')
    result=APIClient().get('/api/search/',{'q':'jak głosował poseł Mariusz Gosek w sprawie kryptowalut'}).json()
    assert result['total']==1
    assert result['direct_results'][0]['id']==wanted.pk
    # Two separate members must not be mistaken for one person.
    result=APIClient().get('/api/search/',{'q':'jak głosował poseł Jan Gosek'}).json()
    assert result['total']==0
    assert result['direct_results']==[]

def test_generic_search_unchanged_and_filters_apply(votes):
    votes(1,'Mariusz Gosek')
    client=APIClient()
    result=client.get('/api/search/',{'q':'Gosek'}).json()
    assert result['total']==1
    assert 'direct_results' not in result
    result=client.get('/api/search/',{'q':'jak glosowal posel Gosek','categories':'article'}).json()
    assert result['total']==0
    assert result['direct_results']==[]
    result=client.get('/api/search/',{'q':'jak głosował poseł Nieznany'}).json()
    assert result['total']==0
