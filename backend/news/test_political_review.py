"""Editorial review panel (three X views) tests. Isolated synthetic data; never a paid X call,
never a Thread publish. Exercises news.political_api on top of already-stored PoliticalPost rows."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from news.models import Article, Thread
from news.political_api import DRAFT_RULES
from news.political_models import PoliticalAccount, PoliticalDraft, PoliticalPost

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def political_review_urls(settings):
    """Use the staff-only political router for every test in this module."""
    settings.ROOT_URLCONF = 'news.political_urls'


@pytest.fixture
def staff():
    return get_user_model().objects.create_user(username='review-editor-fixture', is_staff=True)


@pytest.fixture
def gov_account(staff):
    account = PoliticalAccount.objects.create(user_id='11111', handle='GovFixture', display_name='Gov fixture',
        camp='government', enabled=True, confirmation_url='https://example.org/gov-fixture')
    account.confirm(staff)
    return account


@pytest.fixture
def opp_account(staff):
    account = PoliticalAccount.objects.create(user_id='22222', handle='OppFixture', display_name='Opp fixture',
        camp='opposition', enabled=True, confirmation_url='https://example.org/opp-fixture')
    account.confirm(staff)
    return account


@pytest.fixture
def public_account(staff):
    account = PoliticalAccount.objects.create(user_id='33333', handle='PublicFixture', display_name='Public fixture',
        camp='public', enabled=False, confirmation_url='https://example.org/public-fixture')
    account.confirm(staff)
    return account


def make_post(account, post_id, **extra):
    return PoliticalPost.objects.create(account=account, post_id=str(post_id),
        url=f'https://x.com/{account.handle}/status/{post_id}', text=f'Synthetic post {post_id}; not a claim of truth.',
        published_at=timezone.now() - timedelta(hours=1), source_data={}, author_data={}, media=[],
        response_sha256='0' * 64, camp_at_collection=account.camp, **extra)


@pytest.fixture
def gov_post(gov_account):
    return make_post(gov_account, 101)


@pytest.fixture
def opp_post(opp_account):
    return make_post(opp_account, 201)


@pytest.fixture
def public_post(public_account):
    return make_post(public_account, 301)


def client_as(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def test_government_view_lists_only_government_camp_posts(staff, gov_post, opp_post, public_post):
    response = client_as(staff).get('/posts/?camp=government&available=true')
    ids = [row['id'] for row in response.json()['results']]
    assert response.status_code == 200 and gov_post.pk in ids and opp_post.pk not in ids and public_post.pk not in ids


def test_opposition_view_lists_only_opposition_camp_posts(staff, gov_post, opp_post):
    response = client_as(staff).get('/posts/?camp=opposition&available=true')
    ids = [row['id'] for row in response.json()['results']]
    assert response.status_code == 200 and opp_post.pk in ids and gov_post.pk not in ids


def test_posts_search_by_handle_and_available_filter(staff, gov_post):
    client = client_as(staff)
    found = client.get(f'/posts/?q={gov_post.account.handle}').json()['results']
    assert any(row['id'] == gov_post.pk and row['account_handle'] == gov_post.account.handle for row in found)
    gov_post.available = False
    gov_post.save(update_fields=['available'])
    still_visible = client.get('/posts/').json()['results']
    hidden = client.get('/posts/?available=true').json()['results']
    assert any(row['id'] == gov_post.pk for row in still_visible)
    assert not any(row['id'] == gov_post.pk for row in hidden)


def test_draft_proposal_result_carries_quote_link_account_date_evidence_uncertainty_and_status(staff, gov_post):
    client = client_as(staff)
    payload = {'camp': 'government', 'day': timezone.localdate().isoformat(),
        'title': 'Przekaz obozu rządzącego — testowa propozycja', 'posts': [gov_post.pk],
        'proposed_items': [{'post': gov_post.pk, 'evidence_for': ['https://example.org/dowod-za'],
            'evidence_against': ['https://example.org/dowod-przeciw'],
            'uncertainty': 'Brak potwierdzenia z drugiego, niezależnego źródła.'}]}
    response = client.post('/drafts/', payload, format='json')
    assert response.status_code == 201, response.data
    draft = PoliticalDraft.objects.get(pk=response.data['id'])
    assert draft.status == 'pending_review' and draft.origin == 'editorial_selection'
    packet = client.get(f'/drafts/{draft.pk}/packet/').json()
    source = packet['sources'][0]
    assert source['text'] == gov_post.text and source['url'] == gov_post.url
    assert source['account_handle'] == gov_post.account.handle
    assert packet['proposed_items'][0]['evidence_for'] == ['https://example.org/dowod-za']
    assert packet['proposed_items'][0]['evidence_against'] == ['https://example.org/dowod-przeciw']
    assert packet['proposed_items'][0]['uncertainty']
    assert packet['rules'] == DRAFT_RULES
    assert response.data['status'] == 'pending_review'


def test_proposed_items_reject_evidence_for_a_post_outside_the_selection(staff, gov_post, opp_post):
    payload = {'camp': 'government', 'day': timezone.localdate().isoformat(), 'title': 'Fixture',
        'posts': [gov_post.pk],
        'proposed_items': [{'post': opp_post.pk, 'evidence_for': [], 'evidence_against': [], 'uncertainty': ''}]}
    assert client_as(staff).post('/drafts/', payload, format='json').status_code == 400


def test_proposed_items_reject_oversized_uncertainty_text(staff, gov_post):
    payload = {'camp': 'government', 'day': timezone.localdate().isoformat(), 'title': 'Fixture',
        'posts': [gov_post.pk],
        'proposed_items': [{'post': gov_post.pk, 'evidence_for': [], 'evidence_against': [], 'uncertainty': 'x' * 2001}]}
    assert client_as(staff).post('/drafts/', payload, format='json').status_code == 400


def test_candidates_view_accepts_posts_from_all_account_groups(staff, gov_post, opp_post, public_post):
    client = client_as(staff)
    payload = {'camp': 'government', 'day': timezone.localdate().isoformat(),
        'title': 'Kandydaci Dr Spina — testowa propozycja', 'posts': [gov_post.pk, opp_post.pk, public_post.pk]}
    response = client.post('/drafts/candidates/', payload, format='json')
    assert response.status_code == 201, response.data
    draft = PoliticalDraft.objects.get(pk=response.data['id'])
    assert set(draft.posts.values_list('pk', flat=True)) == {gov_post.pk, opp_post.pk, public_post.pk}
    assert draft.status == 'pending_review' and draft.origin == 'editorial_selection'


def test_regular_drafts_endpoint_still_rejects_mixed_camp_selection(staff, gov_post, opp_post):
    payload = {'camp': 'government', 'day': timezone.localdate().isoformat(), 'title': 'Fixture',
        'posts': [gov_post.pk, opp_post.pk]}
    assert client_as(staff).post('/drafts/', payload, format='json').status_code == 400


def test_candidate_draft_approval_never_publishes_a_thread(staff, gov_post, opp_post):
    client = client_as(staff)
    created = client.post('/drafts/candidates/', {'camp': 'opposition', 'day': timezone.localdate().isoformat(),
        'title': 'Fixture candidates', 'posts': [gov_post.pk, opp_post.pk]}, format='json')
    result = client.post(f"/drafts/{created.data['id']}/review/", {'decision': 'approved'}, format='json')
    assert result.status_code == 200 and result.data['published_threads'] == 0
    assert not Thread.objects.exists() and not Article.objects.exists()


def test_ordinary_authenticated_user_cannot_reach_the_review_panel(staff, gov_post):
    ordinary = get_user_model().objects.create_user(username='not-editor-review-fixture')
    client = client_as(ordinary)
    assert client.get('/posts/?camp=government').status_code == 403
    assert client.post('/drafts/candidates/', {'camp': 'government', 'day': timezone.localdate().isoformat(),
        'title': 'x', 'posts': [gov_post.pk]}, format='json').status_code == 403


def test_draft_list_can_be_filtered_by_camp_and_status_for_the_review_queue(staff, gov_post, opp_post):
    client = client_as(staff)
    client.post('/drafts/', {'camp': 'government', 'day': timezone.localdate().isoformat(), 'title': 'Gov fixture',
        'posts': [gov_post.pk]}, format='json')
    client.post('/drafts/candidates/', {'camp': 'opposition', 'day': timezone.localdate().isoformat(),
        'title': 'Candidates fixture', 'posts': [gov_post.pk, opp_post.pk]}, format='json')
    government_only = client.get('/drafts/?camp=government').json()['results']
    assert government_only and all(row['camp'] == 'government' for row in government_only)
    pending_only = client.get('/drafts/?status=pending_review').json()['results']
    assert pending_only and all(row['status'] == 'pending_review' for row in pending_only)


def test_status_endpoint_exposes_draft_rules_for_the_editorial_panel(staff):
    response = client_as(staff).get('/status/')
    assert response.status_code == 200
    assert response.data['draft_rules'] == DRAFT_RULES
    assert 'Ostateczną decyzję podejmuje redaktor' in response.data['draft_rules']
