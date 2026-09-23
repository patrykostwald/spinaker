import pytest
from rest_framework.test import APIClient

from news.models import Article, Ballot, ParliamentaryVoting, Source
from news.political_models import (ParliamentaryRosterEntry, PoliticalAccount, PoliticalAccountCandidate,
    PoliticalPost, PublicFigure, PublicFigureOrganisationRelation, RegisteredOrganisation, SocialHandleEvidence)


pytestmark = pytest.mark.django_db


def test_profile_exposes_only_confirmed_relationships_and_linked_votes():
    roster = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='17', full_name='Anna Publiczna', active=True, term=10)
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


def test_profile_never_mixes_votes_from_another_term():
    roster = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='17', full_name='Anna Publiczna', active=True, term=10)
    figure = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='parliamentary', role_title='Posłanka',
        evidence_url='https://sejm.example/anna', parliamentary_roster_entry=roster)
    source = Source.objects.create(name='Sejm', url='https://sejm.example')
    for term, motion in [(9, 'Poprzednia kadencja'), (10, 'Obecna kadencja')]:
        article = Article.objects.create(source=source, title=motion, url=f'https://sejm.example/{term}', published_date='2026-09-20T10:00:00Z')
        voting = ParliamentaryVoting.objects.create(article=article, term=term, sitting=1, number=term, motion=motion, kind='vote')
        Ballot.objects.create(voting=voting, mp_id=17, name='Anna Publiczna', vote='Za')
    data = APIClient().get(f'/api/public-figures/{figure.pk}/').data
    assert [row['topic'] for row in data['votes']['results']] == ['Obecna kadencja']


def test_unlinked_figure_does_not_guess_votes_or_show_pending_relation():
    figure = PublicFigure.objects.create(canonical_name='Inna Osoba', role_category='political', role_title='Liderka', evidence_url='https://example.org/person')
    data = APIClient().get(f'/api/public-figures/{figure.pk}/').data
    assert data['votes']['available'] is False
    assert data['organisations'] == []


def test_editing_confirmed_organisation_relation_requires_new_review():
    figure = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='government', role_title='Ministra',
        evidence_url='https://gov.example/anna')
    organisation = RegisteredOrganisation.objects.create(name='Fundacja Jawna', krs_number='0000123456', kind='foundation', official_register_url='https://prs.example/1')
    relation = PublicFigureOrganisationRelation.objects.create(public_figure=figure, organisation=organisation,
        public_role='członkini zarządu', evidence_url='https://example.org/evidence')
    staff = __import__('django.contrib.auth').contrib.auth.get_user_model().objects.create_user(username='editor', is_staff=True)
    relation.confirm(staff)
    relation.public_role = 'członkini rady'
    relation.save(update_fields=['public_role'])
    relation.refresh_from_db()
    assert relation.verification_status == 'pending_review'
    assert relation.verified_by is None
    assert relation.verified_at is None


def test_profile_exposes_x_only_after_public_link_candidate_resolution_and_account_confirmation():
    roster = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='77', full_name='Anna Publiczna', active=True)
    figure = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='parliamentary', role_title='Posłanka',
        evidence_url='https://sejm.example/anna', parliamentary_roster_entry=roster)
    candidate = PoliticalAccountCandidate.objects.create(handle='AnnaPubliczna', display_name='Anna Publiczna',
        classification='independent', confirmation_url='https://sejm.example/anna', confirmation_note='Publiczny link.')
    evidence = SocialHandleEvidence.objects.create(roster_entry=roster, handle='AnnaPubliczna',
        evidence_url='https://sejm.example/anna', extracted_url='https://x.com/AnnaPubliczna', candidate=candidate,
        status='candidate_created')
    assert APIClient().get(f'/api/public-figures/{figure.pk}/').data['x_account'] is None

    staff = __import__('django.contrib.auth').contrib.auth.get_user_model().objects.create_user(
        username='staff', is_staff=True,
    )
    account = PoliticalAccount.objects.create(user_id='77', handle='AnnaPubliczna', display_name='Anna Publiczna',
        camp='public', confirmation_url='https://sejm.example/anna', confirmation_note='Potwierdzone.')
    account.confirm(staff)
    candidate.resolved_account = account
    candidate.save(update_fields=['resolved_account'])
    data = APIClient().get(f'/api/public-figures/{figure.pk}/').data
    assert data['x_account']['handle'] == 'AnnaPubliczna'
    assert data['x_account']['posts_collected'] == 0
    assert data['x_posts'] == {'available': True, 'results': []}

    post = PoliticalPost.objects.create(
        account=account, post_id='123', url='https://x.com/AnnaPubliczna/status/123', text='Wpis z konta',
        published_at='2026-09-23T10:00:00Z', response_sha256='a' * 64,
        source_data={'public_metrics': {'like_count': 7, 'retweet_count': 2}},
    )
    data = APIClient().get(f'/api/public-figures/{figure.pk}/').data
    assert data['x_posts']['results'] == [{
        'id': post.pk, 'post_id': '123', 'url': 'https://x.com/AnnaPubliczna/status/123',
        'text': 'Wpis z konta', 'published_at': post.published_at,
        'likes_count': 7, 'reposts_count': 2,
    }]
