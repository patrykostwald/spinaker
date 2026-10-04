from datetime import timedelta
from io import BytesIO
from importlib import import_module
from unittest.mock import Mock
from types import SimpleNamespace

import pytest
from PIL import Image
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError, PermissionDenied

from news.account_models import AccountIdentity, PersonalContextThread, PersonalContextThreadItem
from news.community_models import CommunityLink, CommunityThreadOpinion, CommunityThreadReport
from news.thread_social_models import ThreadComment, ThreadRateEvent, ThreadModerationReport, ThreadModerationDecision, ThreadModerationMail
from news.thread_moderation import decide, deliver_mail, assess_report, screen_report
from news.diagnosis_threads import short

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def offline(settings, monkeypatch):
    settings.THREADS_ENABLED = settings.ACCOUNTS_ENABLED = True
    def forbidden(*args, **kwargs):
        pytest.fail('No real HTTP/SMTP is allowed in social tests.')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('smtplib.SMTP_SSL', forbidden)
    monkeypatch.setattr('news.thread_moderation.screen_report', lambda body: {'state': 'unavailable'})
    monkeypatch.setattr('news.account_mail.send_account_mail', lambda *args: False)


def user(name='reader', verified=True, staff=False):
    row = get_user_model().objects.create_user(name, is_staff=staff, is_superuser=staff)
    AccountIdentity.objects.create(user=row, email=f'{name}@example.org', email_verified=verified)
    return row


@pytest.fixture
def setup():
    author = user('author')
    reader = user()
    thread = PersonalContextThread.objects.create(owner=author, title='Nitka', is_public=True, published_at=timezone.now())
    for i in range(3):
        link = CommunityLink.objects.create(canonical_url=f'https://example.org/{i}', domain='example.org', title=f'Boks {i}')
        PersonalContextThreadItem.objects.create(thread=thread, link=link, position=i)
    client = APIClient()
    client.force_authenticate(reader)
    return client, thread, reader, author, f'/api/community/threads/{thread.pk}/'


def test_vote_unique_change_verified_distribution(setup):
    """Spinkę ocenia się krok po kroku; ocena całości to średnia z przejścia wszystkich kroków (właściciel 3.10)."""
    client, thread, reader, _, base = setup
    assert client.get(base+'opinions/').data['distribution'] == {'positive': 0, 'doubt': 0, 'negative': 0}
    assert client.post(base+'opinions/', {'polarity': 'positive'}).status_code == 400
    items = list(thread.items.values_list('pk', flat=True))
    # wynik liczą tylko spinki (powiązania między boksami): przy 3 boksach są 2 takie kroki
    step = lambda item, polarity: client.post(base+'steps/', {'item_id': item, 'part': 'context', 'polarity': polarity})
    assert step(items[1], 'positive').data['progress'] == {'done': 1, 'total': 2}
    assert not CommunityThreadOpinion.objects.filter(thread=thread, user=reader).exists()
    result = step(items[2], 'negative').data
    assert result['progress'] == {'done': 2, 'total': 2} and result['score'] == {'percent': 50, 'reactions': 2}
    assert CommunityThreadOpinion.objects.get(thread=thread, user=reader).polarity == 'doubt'
    step(items[1], 'negative')
    assert CommunityThreadOpinion.objects.get(thread=thread, user=reader).polarity == 'negative'
    assert step(items[1], 'negative').data['progress']['done'] == 1
    assert not CommunityThreadOpinion.objects.filter(thread=thread, user=reader).exists()
    assert client.post(base+'steps/', {'item_id': 999999, 'part': 'context', 'polarity': 'positive'}).status_code == 400
    assert client.post(base+'steps/', {'item_id': items[0], 'part': 'context', 'polarity': 'positive'}).status_code == 400
    # reakcje na boksy (kolor kwadratów na liście) są przyjmowane, ale nie zmieniają wyniku spinki ani postępu
    boxed = client.post(base+'steps/', {'item_id': items[0], 'part': 'box', 'polarity': 'positive'})
    assert boxed.status_code == 200 and boxed.data['progress'] == {'done': 1, 'total': 2}
    assert boxed.data['score'] == {'percent': 0, 'reactions': 1}
    assert [row['part'] for row in boxed.data['steps']] == ['box', 'context', 'box', 'context', 'box']
    step(items[1], 'negative')
    assert CommunityThreadOpinion.objects.get(thread=thread, user=reader).polarity == 'negative'
    for name, rating in [('second', 'positive'), ('third', 'doubt')]:
        CommunityThreadOpinion.objects.create(user=user(name), thread=thread, polarity=rating)
    result = client.get(base+'opinions/').data
    assert result['highlight'] and result['total'] == 3
    assert all(n == pytest.approx(1/3) for n in result['distribution'].values())
    client.force_authenticate(user('unverified', False))
    assert client.post(base+'steps/', {'item_id': items[1], 'part': 'context', 'polarity': 'positive'}).status_code == 403
    assert client.post(base+'comments/', {'body': 'Text'}).status_code == 403
    client.force_authenticate(None)
    assert client.post(base+'opinions/', {'polarity': 'positive'}).status_code in (401, 403)


@pytest.mark.parametrize('threads,accounts', [(True, False), (False, True), (False, False)])
def test_flags(setup, settings, threads, accounts):
    client, _, _, _, base = setup
    settings.THREADS_ENABLED, settings.ACCOUNTS_ENABLED = threads, accounts
    for endpoint in ('', 'opinions/', 'comments/', 'card.png'):
        assert client.get(base+endpoint).status_code == (200 if threads else 404)
    for endpoint, data in [('opinions/', {'polarity': 'positive'}), ('comments/', {'body': 'abc'}), ('report/', {'reason': 'spam'})]:
        assert client.post(base+endpoint, data).status_code == 404


def test_comment_limit_edit_delete_and_references(setup):
    client, thread, reader, author, base = setup
    assert client.post(base+'comments/', {'body': 'x'*2001}).status_code == 400
    assert client.post(base+'comments/', {'body': ' '}).status_code == 400
    response = client.post(base+'comments/', {'body': '@boks 3 '+ 'x'*592})
    assert response.status_code == 201 and response.data['box_references'] == [3]
    row = ThreadComment.objects.get(pk=response.data['id'])
    url = base+f'comments/{row.pk}/'
    assert client.patch(url, {'body': '@boks 2'}).status_code == 200
    row.refresh_from_db()
    assert row.edited_at and row.body == '@boks 2'
    ThreadComment.objects.filter(pk=row.pk).update(created_at=timezone.now()-timedelta(minutes=5))
    assert client.patch(url, {'body': 'late'}).status_code == 403
    client.force_authenticate(author)
    assert client.delete(url).status_code == 404
    client.force_authenticate(reader)
    thread.hidden_at = timezone.now(); thread.save()
    assert client.delete(url).status_code == 204
    row.refresh_from_db()
    assert row.deleted_at and row.body == ''
    assert ThreadRateEvent.objects.filter(kind='comment').count() == 2


def test_comment_paging_count_sort_stable_after_delete(setup):
    client, thread, reader, _, base = setup
    other = PersonalContextThread.objects.create(owner=reader, title='Other', is_public=True, published_at=timezone.now())
    for item in thread.items.all():
        PersonalContextThreadItem.objects.create(thread=other, link=item.link, position=item.position)
    ThreadComment.objects.create(thread=other, author=reader, body='older')
    rows = [ThreadComment.objects.create(thread=thread, author=reader, body=str(i)) for i in range(22)]
    first = client.get(base+'comments/').data
    assert [r['body'] for r in first['results']] == [str(i) for i in range(21, 1, -1)]
    assert first['count'] == 22
    client.delete(base+f'comments/{rows[-1].pk}/')
    second = client.get(base+f"comments/?after={first['next_cursor']}").data
    assert [r['body'] for r in second['results']] == ['1', '0']
    assert second['next_cursor'] is None
    result = client.get('/api/community/threads/?sort=comments').data['results']
    assert result[0]['id'] == thread.pk and result[0]['comments_count'] == 21
    ThreadComment.objects.filter(thread=thread).update(hidden_at=timezone.now())
    assert client.get('/api/community/threads/?sort=comments').data['results'][0]['id'] == other.pk
    assert client.get(base+'comments/?after=bad').status_code == 400


@pytest.mark.parametrize('kind,limit,endpoint,payload', [('comment',20,'comments/',{'body':'test'}),('rating',50,'steps/',{'part':'context','polarity':'doubt'})])
def test_durable_account_limits(setup, kind, limit, endpoint, payload):
    client, thread, reader, _, base = setup
    if kind == 'rating':
        payload = {**payload, 'item_id': thread.items.all()[1].pk}
    ThreadRateEvent.objects.bulk_create([ThreadRateEvent(user=reader, kind=kind) for _ in range(limit-1)])
    assert client.post(base+endpoint, payload).status_code in (200,201)
    if kind == 'comment':
        row = ThreadComment.objects.get(author=reader)
        assert client.delete(base+f'comments/{row.pk}/').status_code == 204
    assert client.post(base+endpoint, payload).status_code == 429
    ThreadRateEvent.objects.update(created_at=timezone.now()-timedelta(hours=1,seconds=1))
    assert client.post(base+endpoint, payload).status_code in (200,201)


@pytest.mark.parametrize('comment', [False, True])
@pytest.mark.parametrize('probability,hidden', [(None,False),(.89,False),(.9,True)])
def test_report_screening(setup, monkeypatch, comment, probability, hidden):
    client, thread, _, author, base = setup
    target = ThreadComment.objects.create(thread=thread, author=author, body='Reported text') if comment else thread
    monkeypatch.setattr('news.thread_moderation.screen_report', lambda body: {'state': 'unavailable'} if probability is None else {'state':'assessed','probability':probability,'rule':'N2'})
    url = base+(f'comments/{target.pk}/' if comment else '')+'report/'
    assert client.post(url, {'reason':'abuse','details':'Please review'}).status_code == 201
    target.refresh_from_db()
    assert bool(target.hidden_at) == hidden
    report = ThreadModerationReport.objects.get()
    assert report.status == 'new' and not report.decisions.exists()
    if not hidden:
        assert client.post(url, {'reason':'spam'}).data['status'] == 'already_reported'
    assert ThreadModerationReport.objects.count() == 1


def test_human_decisions_mail_retry_appeal_and_permissions(setup, monkeypatch):
    client, thread, reader, author, base = setup
    result = client.post(base+'report/', {'reason':'spam'})
    report = ThreadModerationReport.objects.get(pk=result.data['id'])
    moderator, reviewer = user('moderator',staff=True), user('reviewer',staff=True)
    with pytest.raises(PermissionDenied): decide(report.pk, reader, 'hide', 'N4', 'Reason')
    with pytest.raises(ValidationError): decide(report.pk, moderator, 'hide', 'N4', '')
    decision = decide(report.pk, moderator, 'hide', 'N4', 'Repeated advertising')
    assert ThreadModerationMail.objects.count() == 2
    deliver_mail()
    assert ThreadModerationMail.objects.filter(sent_at__isnull=True).count() == 2
    send = Mock(return_value=True); monkeypatch.setattr('news.account_mail.send_account_mail', send)
    deliver_mail(); deliver_mail()
    assert send.call_count == 2
    assert set(call.args[0] for call in send.call_args_list) == {'reader@example.org','author@example.org'}
    assert 'N4' in send.call_args.args[2] and f'/spinki/odwolanie/{report.pk}' in send.call_args.args[2]
    url = f'/api/community/reports/{report.pk}/'
    client.force_authenticate(user('stranger'))
    assert client.get(url).status_code == 403
    assert client.post(url, {'body':'appeal'}).status_code == 403
    client.force_authenticate(author)
    assert client.get(url).data['decisions'][0]['explanation'] == decision.explanation
    assert client.post(url, {'body':'Not advertising'}).status_code == 200
    assert client.post(url, {'body':'Again'}).status_code == 400
    with pytest.raises(ValidationError): decide(report.pk, moderator, 'restore', 'N5', 'Appeal accepted')
    decide(report.pk, reviewer, 'restore', 'N5', 'Appeal accepted')
    thread.refresh_from_db(); assert thread.hidden_at is None
    assert ThreadModerationDecision.objects.count() == 2
    assert client.post(url, {'body':'Again'}).status_code == 400
    assess_report(report.pk)  # Late AI response must not hide restored content.
    thread.refresh_from_db(); assert thread.hidden_at is None


def test_write_limits_and_legacy_data_preserved(setup):
    client, thread, reader, _, base = setup
    assert client.post('/api/account/context-threads/', {'title':'x'*66}).status_code == 400
    assert client.post('/api/account/context-threads/', {'title':'x'*65, 'description': 'y'*170}).status_code == 201
    assert client.post('/api/account/context-threads/', {'title':'Test', 'description': 'y'*171}).status_code == 400
    item = thread.items.first()
    for field, limit in [('note',4000),('link_note',200)]:
        payload = {'title':'Test','items':[{'link_id':item.link_id,field:'x'*(limit+1)}]}
        assert client.post('/api/account/context-threads/', payload, format='json').status_code == 400
    thread.title='x'*140;thread.save()
    item.note='y'*800;item.link_note='';item.save()
    CommunityThreadOpinion.objects.create(thread=thread,user=reader,polarity='positive',body='old comment')
    CommunityThreadReport.objects.create(thread=thread,reporter=reader,reason='spam')
    migration=import_module('news.migrations.0113_thread_social_085')
    migration.preserve_legacy(apps, SimpleNamespace(connection=connection))
    assert ThreadComment.objects.get().body == 'old comment'
    assert ThreadModerationReport.objects.get().status == 'new'
    thread.refresh_from_db();item.refresh_from_db()
    assert len(thread.title)==140 and len(item.note)==800


def test_ai_sentence_limits_and_cards(setup):
    client, thread, _, _, base = setup
    assert short('First sentence. '+ 'word '*90,80)=='First sentence.'
    assert len(short('x'*1000,80))<=80
    for format,size in [('og',(1200,630)),('story',(1080,1920))]:
        response=client.get(base+'card.png?layout='+format)
        assert response.status_code==200 and response['Content-Type']=='image/png'
        assert Image.open(BytesIO(response.content)).size==size
    thread.hidden_at=timezone.now();thread.save()
    assert client.get(base+'card.png').status_code==404


def test_moderation_panel_permissions_and_deleted_thread_audit(setup):
    client, thread, reader, author, base = setup
    report_id = client.post(base+'report/', {'reason':'spam'}).data['id']
    url = '/api/community/moderation/'
    assert client.get(url).status_code == 403
    limited = get_user_model().objects.create_user('limited', is_staff=True)
    client.force_authenticate(limited)
    assert client.get(url).status_code == 403
    client.force_authenticate(user('staff', staff=True))
    assert client.get(url).data['results'][0]['id'] == report_id
    assert client.post(url, {'report_id':report_id,'action':'hide','rule':'N4','explanation':''}).status_code == 400
    assert client.post(url, {'report_id':report_id,'action':'hide','rule':'N4','explanation':'Spam'}).status_code == 200
    assert client.get(url).data['results'] == []
    client.force_authenticate(author)
    assert client.delete(f'/api/account/context-threads/{thread.pk}/').status_code == 204
    report = ThreadModerationReport.objects.get(pk=report_id)
    assert report.thread_id is None and report.snapshot and report.decisions.count() == 1
    assert client.post(f'/api/community/reports/{report_id}/', {'body':'Odwołanie po usunięciu spinki'}).status_code == 200


def test_hidden_comment_visible_only_to_owner_and_deletable(setup):
    client, thread, reader, author, base = setup
    row = ThreadComment.objects.create(thread=thread, author=reader, body='Hidden', hidden_at=timezone.now())
    data = client.get(base+'comments/').data
    assert data['count'] == 0 and data['results'][0]['hidden'] and not data['results'][0]['can_edit']
    client.force_authenticate(author)
    assert client.get(base+'comments/').data['results'] == []
    client.force_authenticate(reader)
    AccountIdentity.objects.filter(user=reader).update(email_verified=False)
    assert client.delete(base+f'comments/{row.pk}/').status_code == 204


@pytest.mark.parametrize('result,expected', [({'probability':.95,'rule':'N2'},'assessed'),({'probability':float('nan'),'rule':'N2'},'unavailable'),({'probability':1,'rule':'bad'},'unavailable')])
def test_free_model_response_validation(monkeypatch, result, expected):
    monkeypatch.setattr('news.clinic_moderation.registry.available', lambda member: True)
    monkeypatch.setattr('news.clinic_moderation.registry.reserve', lambda member: True)
    monkeypatch.setattr('news.clinic_moderation.registry.credentials', lambda provider: 'test-only')
    response = Mock()
    import json
    response.json.return_value = {'choices':[{'message':{'content':json.dumps(result)}}]}
    request = Mock(return_value=response)
    monkeypatch.setattr('news.clinic_moderation.requests.post', request)
    assert screen_report('Untrusted comment')['state'] == expected
    assert request.call_args.kwargs['json']['model'] == 'openai/gpt-oss-20b'


def test_comment_notification_not_rating_and_hidden_suppressed(setup, settings):
    from news.notification_models import NotificationEvent, Notification
    from news.notification_tasks import process_notification_events
    settings.PUSH_ENABLED = False
    client, thread, reader, author, base = setup
    NotificationEvent.objects.all().delete()
    client.post(base+'opinions/', {'polarity':'positive'})
    assert not NotificationEvent.objects.exists()
    response = client.post(base+'comments/', {'body':'New reply'})
    assert NotificationEvent.objects.get().kind == 'thread_comment'
    process_notification_events()
    assert Notification.objects.filter(user=author,kind='thread_reply').count() == 1
    response = client.post(base+'comments/', {'body':'Hidden before delivery'})
    ThreadComment.objects.filter(pk=response.data['id']).update(hidden_at=timezone.now())
    process_notification_events()
    assert Notification.objects.filter(user=author,kind='thread_reply').count() == 1


def test_comment_carries_author_stance_for_coloring(settings):
    """Komentarz niesie ocenę spinki wystawioną przez autora (front koloruje nią pierwsze zdanie)."""
    from news.thread_social import author_stances, comment_data
    from news.community_models import CommunityThreadOpinion
    import inspect
    assert 'stance' in inspect.signature(comment_data).parameters
    assert author_stances(10**9, []) == {}
    assert CommunityThreadOpinion._meta.get_field('polarity')


def _voters(n, prefix, days_old=2):
    rows = []
    for i in range(n):
        row = user(f'{prefix}{i}')
        get_user_model().objects.filter(pk=row.pk).update(date_joined=timezone.now() - timedelta(days=days_old))
        rows.append(row)
    return rows


def test_admission_thresholds_window_and_source_filter(setup, settings):
    settings.ADMISSION_FIRST_ACTIVITY = False
    from news.admission import check_admission, progress
    from news.community_models import CommunityThreadOpinion
    client, thread, reader, author, base = setup
    list_url = '/api/community/threads/'
    ids = lambda source: [r['id'] for r in client.get(list_url, {'source': source}).data['results']]
    assert thread.pk in ids('izba') and thread.pk not in ids('all') and thread.pk not in ids('readers')
    # 9 ✓ to za mało; ✓ od kont młodszych niż doba się nie liczą
    for voter in _voters(9, 'yes'):
        CommunityThreadOpinion.objects.create(user=voter, thread=thread, polarity='positive')
    for voter in _voters(3, 'fresh', days_old=0):
        CommunityThreadOpinion.objects.create(user=voter, thread=thread, polarity='positive')
    assert progress(thread)['positive'] == 9 and not check_admission(thread)
    # 10. ✓, ale za dużo ✕ (poniżej 60% ✓)
    for voter in _voters(1, 'ten'):
        CommunityThreadOpinion.objects.create(user=voter, thread=thread, polarity='positive')
    for voter in _voters(7, 'no'):
        CommunityThreadOpinion.objects.create(user=voter, thread=thread, polarity='negative')
    assert progress(thread)['ratio'] < .6 and not check_admission(thread)
    CommunityThreadOpinion.objects.filter(user__username__startswith='no').delete()
    thread.refresh_from_db()
    assert check_admission(thread)
    thread.refresh_from_db()
    assert thread.admitted_at and thread.pk in ids('all') and thread.pk in ids('readers') and thread.pk not in ids('izba')
    assert client.get(list_url, {'source': 'zle'}).status_code == 400


def test_admission_window_closes_after_seven_days(setup, settings):
    settings.ADMISSION_FIRST_ACTIVITY = False
    from news.admission import check_admission, progress
    from news.community_models import CommunityThreadOpinion
    client, thread, *_ = setup
    PersonalContextThread.objects.filter(pk=thread.pk).update(published_at=timezone.now() - timedelta(days=8))
    thread.refresh_from_db()
    for voter in _voters(10, 'late'):
        CommunityThreadOpinion.objects.create(user=voter, thread=thread, polarity='positive')
    assert not progress(thread)['open'] and not check_admission(thread)
    assert thread.pk not in [r['id'] for r in client.get('/api/community/threads/', {'source': 'izba'}).data['results']]


def test_nick_color_only_for_x_connected_accounts(setup):
    """Kolor nicka (właściciel 3.10) tylko po połączeniu konta z X; konto z samym e-mailem zostaje białe."""
    from news.account_models import UserXConnection
    client, thread, reader, _, base = setup
    assert client.patch('/api/account/profile/', {'nick_color': '#4a9eff'}, format='json').status_code == 400
    UserXConnection.objects.create(user=reader, x_user_id='1', username='czytelnik')
    reader.refresh_from_db()
    assert client.patch('/api/account/profile/', {'nick_color': '#123456'}, format='json').status_code == 400
    data = client.patch('/api/account/profile/', {'nick_color': '#4a9eff'}, format='json').json()
    assert data['nick_color'] == '#4a9eff' and data['can_color_nick']
    ThreadComment.objects.create(thread=thread, author=reader, body='Kolorowy nick')
    assert client.get(base+'comments/').json()['results'][0]['author_color'] == '#4a9eff'


def test_admission_first_activity_mode(setup, settings):
    """Na start (właściciel 3.10): spinka czytelnika przechodzi na główną po pierwszym komentarzu lub reakcji kogoś innego."""
    from news.admission import check_admission
    settings.ADMISSION_FIRST_ACTIVITY = True
    client, thread, reader, author, base = setup
    PersonalContextThread.objects.filter(pk=thread.pk).update(admitted_at=None)
    thread.refresh_from_db()
    client.force_authenticate(thread.owner)
    client.post(base + 'comments/', {'body': 'Mój własny komentarz'})
    thread.refresh_from_db()
    assert thread.admitted_at is None and not check_admission(thread)
    client.force_authenticate(reader if reader.pk != thread.owner_id else author)
    assert client.post(base + 'comments/', {'body': 'Ciekawe zestawienie'}).status_code == 201
    thread.refresh_from_db()
    assert thread.admitted_at is not None
