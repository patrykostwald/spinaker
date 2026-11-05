import pytest
from rest_framework.test import APIClient
from django.contrib.contenttypes.models import ContentType

from news.models import Article, Ballot, ParliamentaryVoting, Source
from news.political_models import (ParliamentaryRosterEntry, PoliticalAccount, PoliticalAccountCandidate,
    PoliticalPost, PublicFigure, PublicFigureArticleReference, PublicFigureOrganisationRelation,
    RegisteredOrganisation, SocialHandleEvidence, OfficialVideoChannel, PublicOffice, PublicFigureRole)


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


def test_profile_stats_are_real_totals_not_the_length_of_a_truncated_list():
    roster = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='17', full_name='Anna Publiczna', active=True, term=10)
    figure = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='parliamentary', role_title='Posłanka',
        evidence_url='https://sejm.example/anna', parliamentary_roster_entry=roster)
    source = Source.objects.create(name='Sejm', url='https://sejm.example')
    for number in range(35):
        article = Article.objects.create(source=source, title=f'G{number}', url=f'https://sejm.example/g{number}', published_date='2026-09-20T10:00:00Z')
        voting = ParliamentaryVoting.objects.create(article=article, term=10, sitting=1, number=number, motion=f'Wniosek {number}', kind='vote')
        Ballot.objects.create(voting=voting, mp_id=17, name='Anna Publiczna', vote='Za')
    data = APIClient().get(f'/api/public-figures/{figure.pk}/').data
    assert len(data['votes']['results']) == 30  # lista pokazuje ostatnie 30
    assert data['stats'] == {'x_posts': None, 'diagnoses': None, 'votes': 35, 'organisations': 0, 'confirmed_materials': 0}


def test_profile_stats_count_x_posts_and_published_diagnoses_of_the_confirmed_account_only():
    from django.utils import timezone
    from news.clinic_models import SpinDiagnosis
    staff = __import__('django.contrib.auth').contrib.auth.get_user_model().objects.create_user(username='staff2', is_staff=True)
    roster = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='78', full_name='Jan Publiczny', active=True)
    figure = PublicFigure.objects.create(canonical_name='Jan Publiczny', role_category='parliamentary', role_title='Poseł',
        evidence_url='https://sejm.example/jan', parliamentary_roster_entry=roster)
    candidate = PoliticalAccountCandidate.objects.create(handle='JanPubliczny', display_name='Jan Publiczny',
        classification='independent', confirmation_url='https://sejm.example/jan', confirmation_note='Publiczny link.')
    SocialHandleEvidence.objects.create(roster_entry=roster, handle='JanPubliczny', evidence_url='https://sejm.example/jan',
        extracted_url='https://x.com/JanPubliczny', candidate=candidate, status='candidate_created')
    account = PoliticalAccount.objects.create(user_id='78', handle='JanPubliczny', display_name='Jan Publiczny', camp='public',
        confirmation_url='https://sejm.example/jan', confirmation_note='Potwierdzone.')
    other = PoliticalAccount.objects.create(user_id='79', handle='Inny', display_name='Inny', camp='public',
        confirmation_url='https://sejm.example/inny', confirmation_note='Potwierdzone.')
    account.confirm(staff)
    candidate.resolved_account = account
    candidate.save(update_fields=['resolved_account'])
    posts = {}
    for owner, number in [(account, 1), (account, 2), (other, 3)]:
        posts[number] = PoliticalPost.objects.create(account=owner, post_id=str(number), url=f'https://x.com/a/status/{number}', text='Wpis',
            published_at='2026-09-23T10:00:00Z', response_sha256=str(number) * 64)
    SpinDiagnosis.objects.create(post=posts[1], status='approved', verdict='spin', intensity=70, headline='A', diagnosed_at=timezone.now())
    SpinDiagnosis.objects.create(post=posts[2], status='pending_review', verdict='spin', intensity=70, headline='B')  # nieopublikowana
    SpinDiagnosis.objects.create(post=posts[3], status='approved', verdict='spin', intensity=70, headline='C', diagnosed_at=timezone.now())  # inne konto
    stats = APIClient().get(f'/api/public-figures/{figure.pk}/').data['stats']
    assert stats['x_posts'] == 2 and stats['diagnoses'] == 1


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


def test_profile_exposes_durable_public_office_separately_from_current_holder():
    figure = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='political',
        role_title='Osoba publiczna', evidence_url='https://example.org/person')
    office = PublicOffice.objects.create(import_key='state-office:test:head', title='Kierownicza funkcja testowa',
        role_category='political', organisation='Instytucja Testowa',
        official_roster_url='https://example.org/official-roster', current_holder=figure)
    PublicFigureRole.objects.create(public_figure=figure, public_office=office,
        role_category='political', role_title=office.title, organisation=office.organisation,
        evidence_url='https://example.org/official-roster')
    data = APIClient().get(f'/api/public-figures/{figure.pk}/').data
    assert data['roles'][0]['office'] == {
        'id': office.pk, 'title': 'Kierownicza funkcja testowa',
        'official_roster_url': 'https://example.org/official-roster',
        'source_checked_at': office.source_checked_at,
    }
    timeline = next(row for row in data['employment_timeline'] if row['office'])
    assert timeline['position'] == 'Kierownicza funkcja testowa'
    assert timeline['source'] == {
        'label': 'Instytucja Testowa', 'url': 'https://example.org/official-roster',
    }
    assert timeline['office']['id'] == office.pk


def test_profile_exposes_only_reviewed_official_youtube_channels():
    figure = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='political',
        role_title='Osoba publiczna', evidence_url='https://example.org/person')
    channel = OfficialVideoChannel.objects.create(
        subject=figure, channel_url='https://www.youtube.com/@AnnaPubliczna',
        display_name='Anna Publiczna', evidence_url='https://example.org/person',
    )
    assert APIClient().get(f'/api/public-figures/{figure.pk}/').data['youtube_channels'] == []

    staff = __import__('django.contrib.auth').contrib.auth.get_user_model().objects.create_user(
        username='youtube-editor', is_staff=True,
    )
    channel.confirm(staff)
    data = APIClient().get(f'/api/public-figures/{figure.pk}/').data
    assert data['youtube_channels'] == [{
        'name': 'Anna Publiczna', 'url': 'https://www.youtube.com/@AnnaPubliczna',
        'channel_id': None, 'evidence_url': 'https://example.org/person',
        'source_checked_at': channel.source_checked_at,
    }]


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
    assert data['x_account']['account_id'] == account.pk
    assert data['x_account']['posts_collected'] == 0
    assert data['x_posts'] == {'available': True, 'results': []}

    post = PoliticalPost.objects.create(
        account=account, post_id='123', url='https://x.com/AnnaPubliczna/status/123', text='Wpis z konta',
        published_at='2026-09-23T10:00:00Z', response_sha256='a' * 64,
        source_data={'public_metrics': {'like_count': 7, 'retweet_count': 2}},
    )
    post.refresh_from_db()
    data = APIClient().get(f'/api/public-figures/{figure.pk}/').data
    assert data['x_posts']['results'] == [{
        'id': post.pk, 'post_id': '123', 'url': 'https://x.com/AnnaPubliczna/status/123',
        'text': 'Wpis z konta', 'published_at': post.published_at,
        'likes_count': 7, 'reposts_count': 2,
    }]


def test_non_parliamentary_figure_exposes_only_generic_confirmed_x_evidence():
    figure = PublicFigure.objects.create(canonical_name='Ministra Publiczna', role_category='government', role_title='Ministra',
        evidence_url='https://gov.example/ministra')
    candidate = PoliticalAccountCandidate.objects.create(handle='MinistraPL', display_name='Ministra Publiczna',
        classification='independent', confirmation_url='https://gov.example/ministra', confirmation_note='Oficjalny link.')
    SocialHandleEvidence.objects.create(
        subject_content_type=ContentType.objects.get_for_model(PublicFigure), subject_object_id=figure.pk,
        handle='MinistraPL', evidence_url='https://gov.example/ministra',
        extracted_url='https://x.com/MinistraPL', candidate=candidate, status='candidate_created',
    )
    assert APIClient().get(f'/api/public-figures/{figure.pk}/').data['x_account'] is None

    staff = __import__('django.contrib.auth').contrib.auth.get_user_model().objects.create_user(username='staff', is_staff=True)
    account = PoliticalAccount.objects.create(user_id='999', handle='MinistraPL', display_name='Ministra Publiczna',
        camp='public', confirmation_url='https://gov.example/ministra', confirmation_note='Potwierdzone.')
    account.confirm(staff)
    candidate.resolved_account = account
    candidate.save(update_fields=['resolved_account'])
    data = APIClient().get(f'/api/public-figures/{figure.pk}/').data
    assert data['x_account'] == {
        'account_id': account.pk,
        'handle': 'MinistraPL', 'url': 'https://x.com/MinistraPL',
        'evidence_url': 'https://gov.example/ministra', 'posts_collected': 0,
    }


def test_public_figure_list_is_paginated_and_filterable():
    for number in range(3):
        PublicFigure.objects.create(canonical_name=f'Osoba {number}', role_category='local', role_title='Prezydent miasta',
            status='current' if number < 2 else 'former', evidence_url=f'https://example.org/{number}')
    client = APIClient()
    first = client.get('/api/public-figures/?role_category=local&status=current&page=1&page_size=1').data
    second = client.get('/api/public-figures/?role_category=local&status=current&page=2&page_size=1').data
    assert first['count'] == 2 and first['page_size'] == 1
    assert [item['name'] for item in first['results']] == ['Osoba 0']
    assert [item['name'] for item in second['results']] == ['Osoba 1']
    assert client.get('/api/public-figures/?page=none').status_code == 400


def test_public_office_list_is_searchable_and_exposes_only_current_holder():
    holder = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='political',
        role_title='Prezeska', evidence_url='https://example.org/anna')
    PublicOffice.objects.create(import_key='state-office:test:one', title='Prezeska instytucji',
        role_category='political', organisation='Instytucja Testowa',
        official_roster_url='https://example.org/roster', current_holder=holder)
    PublicOffice.objects.create(import_key='state-office:test:two', title='Inna funkcja',
        role_category='local', organisation='Miasto Testowe', official_roster_url='https://example.org/city')
    data = APIClient().get('/api/public-offices/?q=Anna&page_size=1').data
    assert data['count'] == 1
    assert data['results'][0]['title'] == 'Prezeska instytucji'
    assert data['results'][0]['current_holder']['name'] == 'Anna Publiczna'


def test_context_exposes_only_confirmed_material_links_and_evidence_graph():
    figure = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='political',
        role_title='Osoba publiczna', evidence_url='https://example.org/person')
    source = Source.objects.create(name='Oficjalne źródło', url='https://example.org')
    article = Article.objects.create(source=source, title='Wywiad z Anną', url='https://example.org/interview',
        category='interview', published_date='2026-09-23T10:00:00Z')
    reference = PublicFigureArticleReference.objects.create(public_figure=figure, article=article,
        reference_kind='interviewee', evidence_note='Osoba występuje w materiale.')
    editor = __import__('django.contrib.auth').contrib.auth.get_user_model().objects.create_user(
        username='research-editor', is_staff=True,
    )
    reference.confirm(editor)
    pending = Article.objects.create(source=source, title='Podobne nazwisko', url='https://example.org/pending')
    PublicFigureArticleReference.objects.create(public_figure=figure, article=pending, reference_kind='mentioned')

    data = APIClient().get(f'/api/public-figures/{figure.pk}/context/').data
    assert data['materials']['count'] == 1
    assert data['materials']['by_category'] == {'interview': 1}
    assert any(edge['type'] == 'confirmed_material_reference' for edge in data['graph']['edges'])
    assert not any(node.get('label') == 'Podobne nazwisko' for node in data['graph']['nodes'])


def test_dossier_returns_only_evidence_pack_and_explicit_ai_contract():
    figure = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='political',
        role_title='Osoba publiczna', evidence_url='https://example.org/person')
    data = APIClient().get(f'/api/public-figures/{figure.pk}/dossier/').data
    assert data['status'] == 'evidence_pack_ready'
    assert data['summary']['confirmed_materials'] == 0
    assert data['research_questions']
    assert data['ai_output_contract']['one_call'] is True
    assert 'nie może dodawać nowych faktów' in data['ai_output_contract']['rule']


def test_public_figure_list_sorts_by_surname_with_polish_alphabet():
    for name in ['Wojciech Zieliński', 'Łukasz Bieniek', 'Anna Łętowska', 'Piotr Lewandowski', 'Marek Zając', 'Joanna Żak', 'Ewa Abacka']:
        PublicFigure.objects.create(canonical_name=name, role_category='parliamentary', role_title='Poseł', evidence_url='https://sejm.example')
    names = [row['name'] for row in APIClient().get('/api/public-figures/').json()['results']]
    assert names == ['Ewa Abacka', 'Łukasz Bieniek', 'Piotr Lewandowski', 'Anna Łętowska', 'Marek Zając', 'Wojciech Zieliński', 'Joanna Żak']
    second = APIClient().get('/api/public-figures/', {'page_size': 3, 'page': 2}).json()['results']
    assert [row['name'] for row in second] == ['Anna Łętowska', 'Marek Zając', 'Wojciech Zieliński']


def test_public_figure_list_filters_by_party_chamber_and_sorts_by_diagnoses():
    def figure(name, club, source):
        entry = ParliamentaryRosterEntry.objects.create(source=source, external_id=name[:3], club=club, term='10')
        return PublicFigure.objects.create(canonical_name=name, role_category='parliamentary', role_title='Poseł',
                                           evidence_url='https://sejm.example', parliamentary_roster_entry=entry)
    figure('Ewa Abacka', 'KO', 'sejm')
    figure('Jan Bielecki', 'PiS', 'sejm')
    figure('Ola Cegła', 'KO', 'senat')
    body = APIClient().get('/api/public-figures/').json()
    assert {row['code']: row['count'] for row in body['facets']['parties']} == {'KO': 2, 'PiS': 1}
    assert {row['code']: row['count'] for row in body['facets']['chambers']} == {'sejm': 2, 'senat': 1}
    ko = APIClient().get('/api/public-figures/', {'party': 'KO'}).json()
    assert [row['name'] for row in ko['results']] == ['Ewa Abacka', 'Ola Cegła'] and ko['results'][0]['party']['short'] == 'KO'
    assert {row['code']: row['count'] for row in ko['facets']['chambers']} == {'sejm': 1, 'senat': 1}
    both = APIClient().get('/api/public-figures/', {'party': 'KO', 'chamber': 'senat'}).json()
    assert [row['name'] for row in both['results']] == ['Ola Cegła'] and both['results'][0]['chamber'] == 'senat'
    assert APIClient().get('/api/public-figures/', {'sort': 'diagnoses'}).json()['results'][0]['diagnoses_count'] == 0
    assert APIClient().get('/api/public-figures/', {'sort': 'zle'}).status_code == 400
