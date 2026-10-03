from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from news import clinic
from news.account_models import AccountIdentity, PersonalContextThread, PersonalContextThreadItem
from news.clinic_models import SpinDiagnosis
from news.community_models import CommunityLink, CommunityThreadOpinion
from news.thread_social_models import ThreadComment
from news.diagnosis_threads import sync_diagnosis_thread
from news.political_models import PoliticalAccount, PoliticalPost

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures('auto_approve_threads')]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Generator nitek nie może wywoływać HTTP ani AI.')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('news.clinic_ai.diagnose', forbidden)
    monkeypatch.setattr('news.clinic_ai._free_chat', forbidden)


def diagnosis(key='1', camp='government', **kwargs):
    account = PoliticalAccount.objects.create(user_id=key, handle=f'posel{key}', display_name='Poseł Test', camp=camp)
    post = PoliticalPost.objects.create(account=account, post_id=key, url=f'https://x.com/posel{key}/status/{key}',
        text='Podatki spadły o połowę.', published_at=timezone.now(), camp_at_collection=camp)
    return SpinDiagnosis.objects.create(post=post, status=kwargs.pop('status', 'approved'), headline='Podatki',
        intensity=72, verdict='spin', techniques=[{'name': 'wybiórczość', 'explanation': 'Pominięto część danych.'}],
        usage={'council': {'members': [{'model': 'a', 'verdict': 'spin'}, {'model': 'b', 'verdict': 'spin'},
                                     {'model': 'c', 'verdict': 'no_spin'}]}}, **kwargs)


def test_diagnosis_thread_full_and_idempotent():
    row = diagnosis(claims=[{'claim': f'Twierdzenie {i}', 'assessment': 'contradicted',
        'explanation': 'Dane mówią inaczej. Drugie zdanie.',
        'sources': [{'url': f'https://stat.gov.pl/{i}', 'title': 'Dane GUS'}]} for i in range(4)])
    thread = row.context_thread
    items = list(thread.items.all())
    assert thread.owner_id is None and thread.is_public
    assert [item.box_data['box_type'] for item in items] == ['post', 'technique', 'claim', 'source', 'claim', 'source', 'claim', 'diagnosis']
    assert items[0].box_data['body'] == row.post.text
    assert items[0].box_data['source_name'] == 'Poseł Test'
    assert items[0].box_data['published_date'] and items[0].box_data['url'] == row.post.url
    assert items[0].link_note == ''
    assert items[1].link_note.startswith('Technika: wybiórczość.')
    assert items[2].box_data['body'] == 'Dane mówią inaczej.'
    assert items[3].link_note == 'Dane mówią inaczej.'
    assert items[-1].link_note == row.headline
    assert items[-1].box_data['url'] == f'/klinika/{row.pk}'
    assert all(len(item.link_note) <= 280 for item in items)
    before = [item.pk for item in items]
    assert sync_diagnosis_thread(row.pk).pk == thread.pk
    assert list(thread.items.values_list('pk', flat=True)) == before
    assert PersonalContextThread.objects.filter(diagnosis=row).count() == 1


def test_diagnosis_thread_without_claims_and_without_council():
    row = diagnosis(claims=[])
    row.usage = {}
    row.save()
    items = list(row.context_thread.items.all())
    assert [item.box_data['box_type'] for item in items] == ['post', 'technique', 'diagnosis']
    assert items[1].link_note.startswith('Technika:')
    assert items[-1].link_note == row.headline


def test_diagnosis_thread_claim_without_sources_and_moderation_survives_sync():
    row = diagnosis(claims=[{'claim': 'Deklaracja', 'assessment': 'unverified', 'explanation': 'Brak danych.', 'sources': []}])
    thread = row.context_thread
    assert [i.box_data['box_type'] for i in thread.items.all()] == ['post', 'technique', 'claim', 'diagnosis']
    thread.hidden_at = timezone.now()
    thread.save()
    sync_diagnosis_thread(row.pk)
    thread.refresh_from_db()
    assert thread.hidden_at is not None


def test_community_latest_comment_uses_append_time(settings):
    settings.THREADS_ENABLED = settings.ACCOUNTS_ENABLED = True
    first, second = diagnosis().context_thread, diagnosis('2').context_thread
    reader = get_user_model().objects.create_user('reader')
    AccountIdentity.objects.create(user=reader, email='reader@example.org', email_verified=True)
    old = CommunityThreadOpinion.objects.create(thread=first, user=reader, polarity='positive')
    CommunityThreadOpinion.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=10))
    CommunityThreadOpinion.objects.create(thread=second, user=reader, polarity='positive')
    ThreadComment.objects.create(thread=second, author=reader, body='Wcześniejszy komentarz')
    client = APIClient()
    client.force_authenticate(reader)
    response = client.post(f'/api/community/threads/{first.pk}/comments/', {'body': 'Dopisany komentarz'}, format='json')
    assert response.status_code == 201 and response.data['created_at']
    assert client.get('/api/community/threads/?sort=comments').data['results'][0]['id'] == first.pk
    assert client.get('/api/community/threads/?sort=hot').data['results'][0]['id'] == second.pk


def test_diagnosis_thread_approval_backfill_and_equal_treatment():
    pending = diagnosis(status='pending_review')
    rejected = diagnosis('2', status='rejected')
    assert not PersonalContextThread.objects.exists()
    clinic.review(pending, None, 'approve')
    assert PersonalContextThread.objects.filter(diagnosis=pending).exists()
    other = diagnosis('3', camp='opposition')
    other.context_thread.delete()
    out = StringIO()
    call_command('drspin_diagnosis_threads', since=timezone.localdate().isoformat(), stdout=out)
    call_command('drspin_diagnosis_threads', since=timezone.localdate().isoformat(), stdout=out)
    assert set(PersonalContextThread.objects.values_list('diagnosis_id', flat=True)) == {pending.pk, other.pk}
    assert not PersonalContextThread.objects.filter(diagnosis=rejected).exists()


@pytest.mark.parametrize('reason', ['withdraw', 'hidden', 'post_unavailable', 'bulk_hidden'])
def test_diagnosis_thread_disappears_everywhere(settings, reason):
    settings.THREADS_ENABLED = True
    settings.ACCOUNTS_ENABLED = False
    row = diagnosis()
    thread = row.context_thread
    staff = get_user_model().objects.create_user('staff', is_staff=True)
    if reason == 'withdraw':
        clinic.withdraw(row, staff, 'Korekta')
        thread.refresh_from_db()
        assert not thread.is_public
    elif reason == 'hidden':
        row.hidden_at = timezone.now()
        row.save(update_fields=['hidden_at'])
    elif reason == 'bulk_hidden':
        SpinDiagnosis.objects.filter(pk=row.pk).update(hidden_at=timezone.now())
    else:
        row.post.available = False
        row.post.save(update_fields=['available'])
    client = APIClient()
    assert client.get('/api/community/threads/?sort=hot').data['results'] == []
    assert client.get(f'/api/community/threads/{thread.pk}/').status_code == 404
    assert client.get(f'/api/community/threads/{thread.pk}/opinions/').status_code == 404


def test_community_hot_ranking_mixed_threads_and_comments(settings):
    settings.THREADS_ENABLED = True
    settings.ACCOUNTS_ENABLED = False
    ai = diagnosis().context_thread
    author = get_user_model().objects.create_user('author')
    user = PersonalContextThread.objects.create(owner=author, title='Nitka użytkownika', is_public=True, published_at=timezone.now())
    for i in range(2):
        link = CommunityLink.objects.create(canonical_url=f'https://example.org/{i}', title='Materiał', domain='example.org')
        PersonalContextThreadItem.objects.create(thread=user, link=link, position=i)
    old = CommunityThreadOpinion.objects.create(thread=ai, user=author, polarity='positive')
    CommunityThreadOpinion.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=8))
    client = APIClient()
    hot = '/api/community/threads/?sort=hot'
    assert [t['id'] for t in client.get(hot).data['results']] == [user.pk, ai.pk]
    reader = get_user_model().objects.create_user('reader')
    CommunityThreadOpinion.objects.create(thread=ai, user=reader, polarity='negative')
    ThreadComment.objects.create(thread=ai, author=reader, body='Komentarz')
    rows = client.get(hot).data['results']
    assert [t['id'] for t in rows] == [ai.pk, user.pk]
    assert rows[0]['author'] == 'Dr. Spin (AI)' and rows[0]['is_ai']
    assert len(rows[0]['preview']) == rows[0]['items_count']
    assert not rows[1]['is_ai']
    assert client.get('/api/community/threads/?sort=comments').data['results'][0]['id'] == ai.pk
    assert client.get('/api/community/threads/').data['results'][0]['id'] == ai.pk
    assert client.get('/api/community/threads/?sort=new').data['results'][0]['id'] == user.pk


@pytest.mark.parametrize('threads,accounts', [(True, False), (True, True), (False, True), (False, False)])
def test_community_read_write_flags(settings, threads, accounts):
    settings.THREADS_ENABLED, settings.ACCOUNTS_ENABLED = threads, accounts
    thread = diagnosis().context_thread
    reader = get_user_model().objects.create_user('reader')
    AccountIdentity.objects.create(user=reader, email='reader@example.org', email_verified=True)
    client = APIClient()
    url = f'/api/community/threads/{thread.pk}/'
    assert client.get('/api/community/threads/').status_code == (200 if threads else 404)
    assert client.get(url).status_code == (200 if threads else 404)
    assert client.get(url + 'opinions/').status_code == (200 if threads else 404)
    step = {'item_id': thread.items.first().pk, 'part': 'box', 'polarity': 'positive'}
    assert client.post(url + 'steps/', step).status_code in (401, 403)
    client.force_authenticate(reader)
    assert client.post(url + 'steps/', step).status_code == (200 if threads and accounts else 404)
    assert client.post('/api/account/context-threads/', {'title': 'Szkic'}, format='json').status_code == (201 if threads and accounts else 403)
