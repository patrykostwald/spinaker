import pytest
from rest_framework.test import APIClient

from news.models import Article, Ballot, ParliamentaryVoting, Source
from news.political_models import ParliamentaryRosterEntry, PublicFigure, PublicFigureOrganisationRelation, RegisteredOrganisation


pytestmark = pytest.mark.django_db


def test_profile_exposes_only_confirmed_relationships_and_linked_votes():
    roster = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='17', full_name='Anna Publiczna', active=True)
    figure = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='government', role_title='Ministra',
        evidence_url='https://gov.example/anna', parliamentary_roster_entry=roster)
    organisation = RegisteredOrganisation.objects.create(name='Fundacja Jawna', krs_number='0000123456', kind='foundation', official_register_url='https://prs.example/1')
    relation = PublicFigureOrganisationRelation.objects.create(public_figure=figure, organisation=organisation,
        public_role='członkini zarządu', evidence_url='https://example.org/evidence')
    editor = __import__('django.contrib.auth').contrib.auth.get_user_model().objects.create_user(username='editor', is_staff=True)
    relation.confirm(editor)
    source = Source.objects.create(name='Sejm', url='https://sejm.example')
    article = Article.objects.create(source=source, title='Głosowanie', url='https://sejm.example/vote', published_date='2026-09-20T10:00:00Z')
    voting = ParliamentaryVoting.objects.create(article=article, term=10, sitting=1, number=2, motion='Ustawa o jawności finansowania', kind='vote')
    Ballot.objects.create(voting=voting, mp_id=17, name='Anna Publiczna', vote='Za')
    data = APIClient().get(f'/api/public-figures/{figure.pk}/').data
    assert data['organisations'][0]['name'] == 'Fundacja Jawna'
    assert data['votes']['results'][0]['topic'] == 'Ustawa o jawności finansowania'


def test_unlinked_figure_does_not_guess_votes_or_show_pending_relation():
    figure = PublicFigure.objects.create(canonical_name='Inna Osoba', role_category='political', role_title='Liderka', evidence_url='https://example.org/person')
    data = APIClient().get(f'/api/public-figures/{figure.pk}/').data
    assert data['votes']['available'] is False
    assert data['organisations'] == []
