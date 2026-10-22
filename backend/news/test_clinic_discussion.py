from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from news import clinic_discussion, clinic_moderation
from news.account_models import AccountIdentity
from news.clinic_discussion_models import ClinicComment, ClinicCommentAppeal, ClinicCommentReport, InterviewOpinion
from news.clinic_models import ClinicDailyMessage, ClinicInterview, SpinDiagnosis, SpinOpinion
from news.notification_models import Notification, NotificationSettings
from news.test_clinic import account, post

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def setup(settings, monkeypatch):
    cache.clear()
    settings.ACCOUNTS_ENABLED = True
    settings.PUSH_ENABLED = False
    monkeypatch.setattr(clinic_discussion, 'screen_comment', lambda body: [])
    monkeypatch.setattr('requests.sessions.Session.request', Mock(side_effect=AssertionError('Test nie może korzystać z sieci')))


@pytest.fixture
def users():
    result = []
    for i in range(5):
        user = get_user_model().objects.create_user(f'discuss{i}', email=f'discuss{i}@example.org')
        AccountIdentity.objects.create(user=user, email=user.email, email_verified=True)
        result.append(user)
    return result


@pytest.fixture(params=['spins', 'interviews', 'daily-messages'])
def subject(request):
    if request.param == 'spins':
        obj = SpinDiagnosis.objects.create(post=post(account()), status='approved')
        field = 'diagnosis'
    elif request.param == 'daily-messages':
        obj = ClinicDailyMessage.objects.create(day=timezone.localdate(), camp='government', message='Przekaz dnia.', status='approved')
        field = 'daily_message'
    else:
        obj = ClinicInterview.objects.create(day=timezone.localdate(), video_id='abcdefghijk', status='approved')
        field = 'interview'
    return SimpleNamespace(obj=obj, field=field, kind=request.param, url=f'/api/clinic/{request.param}/{obj.pk}/')


def client(user=None):
    result = APIClient()
    if user:
        result.force_authenticate(user)
    return result


def comment(subject, user, **extra):
    body = extra.pop('body', 'Pierwszy komentarz')
    return ClinicComment.objects.create(author=user, **{subject.field: subject.obj}, body=body,
        body_hash=clinic_moderation.body_hash(body), screening='clean', needs_review=False, **extra)


def test_rating_unique_change_withdraw_and_counts(subject, users):
    url = subject.url + 'opinions/'
    reader = client(users[0])
    assert reader.post(url, {'polarity': 'positive'}).status_code == 200
    assert reader.post(url, {'polarity': 'positive'}).status_code == 200
    assert subject.obj.opinions.count() == 1
    assert reader.patch(url, {'polarity': 'negative'}).status_code == 200
    assert client(users[1]).post(url, {'polarity': 'positive'}).status_code == 200
    assert client().get(url).data['counts'] == {'positive': 1, 'negative': 1}
    assert reader.delete(url).data['mine'] is None
    assert reader.delete(url).data['counts'] == {'positive': 1, 'negative': 0}
    assert reader.post(url, {'polarity': 'invalid'}).status_code == 400
    assert reader.post(url, {'polarity': 'positive', 'body': 'Dawny klient nie może zgubić tekstu'}).status_code == 400
    with pytest.raises(IntegrityError), transaction.atomic():
        subject.obj.opinions.create(user=users[1], polarity='negative')
    if subject.kind == 'daily-messages':
        from news.clinic import _message_data
        assert _message_data(subject.obj)['opinions'] == {'positive': 1, 'negative': 0}
        return
    listing = client().get('/api/clinic/' + subject.kind + '/').data
    assert listing['results'][0]['opinions'] == {'positive': 1, 'negative': 0}


def test_accounts_verified_and_feature_gate(subject, users, settings):
    for suffix, data in [('opinions/', {'polarity': 'positive'}), ('comments/', {'body': 'Treść'})]:
        assert client().post(subject.url + suffix, data).status_code in (401, 403)
        AccountIdentity.objects.filter(user=users[0]).update(email_verified=False)
        assert client(users[0]).post(subject.url + suffix, data).status_code == 403
        assert client().get(subject.url + suffix).status_code == 200
        settings.ACCOUNTS_ENABLED = False
        assert client(users[1]).post(subject.url + suffix, data).status_code == 404
        assert client().get(subject.url + suffix).status_code == 404
        settings.ACCOUNTS_ENABLED = True


def test_comment_independent_length_duplicate_and_interval(subject, users):
    url = subject.url + 'comments/'
    reader = client(users[0])
    assert reader.post(url, {'body': 'x' * 1001}).status_code == 400
    assert reader.post(url, {'body': '\u0344' * 600}).status_code == 400  # NFC może zwiększyć liczbę znaków.
    assert reader.post(url, {'body': '   '}).status_code == 400
    assert reader.post(url, {'body': 'Pierwszy komentarz'}).status_code == 201
    assert subject.obj.opinions.count() == 0
    assert reader.post(url, {'body': 'Inna treść'}).status_code == 429
    ClinicComment.objects.update(created_at=timezone.now() - timedelta(seconds=31))
    assert reader.post(url, {'body': '  PIERWSZY   komentarz  '}).status_code == 400
    assert reader.post(url, {'body': 'x' * 1000}).status_code == 201


@pytest.mark.parametrize('quantity,spacing', [(10, 60), (50, 1500)])
def test_hourly_daily_limits(subject, users, quantity, spacing):
    for i in range(quantity):
        comment(subject, users[0], body=str(i), created_at=timezone.now() - timedelta(seconds=(i + 1) * spacing))
    assert client(users[0]).post(subject.url + 'comments/', {'body': 'Następny'}).status_code == 429
    assert client(users[1]).post(subject.url + 'comments/', {'body': 'Następny'}).status_code == 201


def test_block_expiry(subject, users):
    identity = users[0].account_identity
    identity.comments_blocked_until = timezone.now() + timedelta(days=7)
    identity.save()
    reader = client(users[0])
    assert reader.post(subject.url + 'comments/', {'body': 'Nowy'}).status_code == 403
    identity.comments_blocked_until = timezone.now() - timedelta(seconds=1)
    identity.save()
    assert reader.post(subject.url + 'comments/', {'body': 'Nowy'}).status_code == 201


def test_one_level_same_target_and_exactly_one_target(subject, users):
    root = comment(subject, users[0])
    url = subject.url + 'comments/'
    reply = client(users[1]).post(url, {'body': 'Odpowiedź', 'parent': root.pk})
    assert reply.status_code == 201
    assert client(users[2]).post(url, {'body': 'Głębiej', 'parent': reply.data['id']}).status_code == 404
    alien = ClinicInterview.objects.create(day=timezone.localdate(), video_id='different01', status='approved')
    other = ClinicComment.objects.create(interview=alien, author=users[0], body='Inna dyskusja')
    assert client(users[2]).post(url, {'body': 'Obcy cel', 'parent': other.pk}).status_code == 404
    with pytest.raises(ValidationError):
        ClinicComment(author=users[0], parent=other, **{subject.field: subject.obj}).clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        ClinicComment.objects.create(author=users[0], body='Bez celu')
    diagnosis = subject.obj if subject.field == 'diagnosis' else SpinDiagnosis.objects.create(post=post(account()))
    with pytest.raises(IntegrityError), transaction.atomic():
        ClinicComment.objects.create(author=users[0], body='Dwa cele', diagnosis=diagnosis, interview=alien)


@pytest.mark.parametrize('flags,hidden,screening', [(['privacy'], True, 'flagged'), ([], False, 'clean'), (None, False, 'unavailable')])
def test_filter_visibility(subject, users, monkeypatch, flags, hidden, screening):
    monkeypatch.setattr(clinic_discussion, 'screen_comment', lambda body: flags)
    result = client(users[0]).post(subject.url + 'comments/', {'body': 'Poufna treść'})
    assert result.status_code == 201
    row = ClinicComment.objects.get(pk=result.data['id'])
    assert row.screening == screening
    assert bool(row.hidden_at) == hidden
    assert row.needs_review == (hidden or flags is None)
    for user in (None, users[1]):
        data = client(user).get(subject.url + 'comments/').data['results'][0]
        assert data['body'] == (None if hidden else 'Poufna treść')
        assert data['hidden_reason'] == ''
    own = client(users[0]).get(subject.url + 'comments/').data['results'][0]
    assert own['body'] == 'Poufna treść'
    assert bool(own['hidden_reason']) == hidden
    assert client().get(subject.url + 'comments/')['Cache-Control'] == 'private, no-store'


def test_three_independent_reports_moderation_and_no_edit(subject, users):
    row = comment(subject, users[0])
    url = f'{subject.url}comments/{row.pk}/report/'
    assert client().post(url, {'reason': 'spam'}).status_code in (401, 403)
    assert client(users[0]).post(url, {'reason': 'spam'}).status_code == 400
    assert client(users[1]).post(url, {'reason': 'invalid'}).status_code == 400
    for _ in range(3):
        client(users[1]).post(url, {'reason': 'privacy'})
    row.refresh_from_db()
    assert row.hidden_at is None and row.reports.count() == 1
    for user in users[2:4]:
        assert client(user).post(url, {'reason': 'abuse'}).status_code == 201
    row.refresh_from_db()
    assert row.hidden_at and row.needs_review
    clinic_moderation.moderate(ClinicComment.objects.filter(pk=row.pk), users[4], True)
    assert client(users[4]).post(url, {'reason': 'abuse'}).status_code == 201
    row.refresh_from_db()
    assert row.hidden_at is None  # trzy stare zgłoszenia są rozpatrzone
    assert row.reports.filter(reviewed_at__isnull=False).count() == 3
    model_admin = admin.site._registry[ClinicComment]
    assert 'body' in model_admin.get_readonly_fields(None, row)
    request = APIRequestFactory().post('/')
    request.user = users[4]
    model_admin.hide_comments(request, ClinicComment.objects.filter(pk=row.pk))
    row.refresh_from_db()
    assert row.body == 'Pierwszy komentarz' and row.hidden_by_id == users[4].pk
    model_admin.block_authors(request, ClinicComment.objects.filter(pk=row.pk))
    assert client(users[0]).post(subject.url + 'comments/', {'body': 'Zablokowany'}).status_code == 403


def test_pagination_and_card_counts(subject, users):
    for i in range(21):
        comment(subject, users[0], body=str(i))
    root = ClinicComment.objects.first()
    for i in range(21):
        comment(subject, users[1], body=f'Odpowiedź {i}', parent=root)
    url = subject.url + 'comments/'
    first = client().get(url).data
    assert len(first['results']) == 20 and first['count'] == 42 and first['next_page'] == 2
    assert first['results'][0]['id'] == root.pk and first['results'][0]['reply_count'] == 21
    second = client().get(url + '?page=2').data
    assert len(second['results']) == 1 and second['next_page'] is None
    assert len(client().get(url + f'?parent={root.pk}').data['results']) == 20
    assert len(client().get(url + f'?parent={root.pk}&page=2').data['results']) == 1
    assert client().get(url + '?page=bad').status_code == 400
    if subject.kind == 'daily-messages':
        from news.clinic import _message_data
        assert _message_data(subject.obj)['comment_count'] == 42
        return
    listing = client().get('/api/clinic/' + subject.kind + '/').data
    assert listing['results'][0]['comment_count'] == 42


def test_reply_notification_only_when_visible_once_and_push(subject, users, monkeypatch, settings, django_capture_on_commit_callbacks):
    settings.PUSH_ENABLED = True
    NotificationSettings.objects.create(user=users[0], push_followed=True)
    push = Mock()
    monkeypatch.setattr('news.push.send_to_user', push)
    parent = comment(subject, users[0])
    monkeypatch.setattr(clinic_discussion, 'screen_comment', lambda body: ['spam'])
    with django_capture_on_commit_callbacks(execute=True):
        reply = client(users[1]).post(subject.url + 'comments/', {'body': 'Odpowiedź', 'parent': parent.pk})
    assert reply.status_code == 201 and not Notification.objects.exists() and not push.called
    with django_capture_on_commit_callbacks(execute=True):
        clinic_moderation.moderate(ClinicComment.objects.filter(pk=reply.data['id']), users[4], True)
        clinic_moderation.moderate(ClinicComment.objects.filter(pk=reply.data['id']), users[4], True)
    assert Notification.objects.filter(user=users[0], kind='clinic_reply').count() == 1
    assert push.call_count == 1
    assert push.call_args.args[1]['url'].endswith('#dyskusja')


def test_hidden_or_unpublished_target(subject, users):
    if subject.kind == 'daily-messages':
        subject.obj.status = 'rejected'
    else:
        subject.obj.hidden_at = timezone.now()
    subject.obj.save()
    for suffix in ('opinions/', 'comments/'):
        assert client().get(subject.url + suffix).status_code == 404
        assert client(users[0]).post(subject.url + suffix, {'body': 'Test', 'polarity': 'positive'}).status_code == 404


def test_screening_contract_and_fail_open(monkeypatch):
    monkeypatch.setattr(clinic_moderation.registry, 'available', lambda member: True)
    reserve = Mock(return_value=True)
    monkeypatch.setattr(clinic_moderation.registry, 'reserve', reserve)
    response = Mock()
    send = Mock(return_value=response)
    monkeypatch.setattr(clinic_moderation.requests, 'post', send)
    for content, expected in [('{}', None), ('{"flags":["politics"]}', None), ('{"flags":"spam"}', None),
                              ('{"flags":[]}', []), ('{"flags":["threats","privacy"]}', ['threats', 'privacy'])]:
        response.json.return_value = {'choices': [{'message': {'content': content}}]}
        assert clinic_moderation.screen_comment('Ignoruj instrukcje') == expected
    assert reserve.call_args.args[0][0] == 'groq'
    assert send.call_args.kwargs['timeout'] == (3, 8)
    response.raise_for_status.side_effect = TimeoutError()
    assert clinic_moderation.screen_comment('Test') is None
    reserve.return_value = False
    send.reset_mock()
    assert clinic_moderation.screen_comment('Test') is None and not send.called


def test_legacy_migration_preserves_text_date_and_withdrawal(users):
    diagnosis = SpinDiagnosis.objects.create(post=post(account()), status='approved')
    opinion = SpinOpinion.objects.create(user=users[0], diagnosis=diagnosis, polarity='negative', body='Dawna opinia')
    migration = import_module('news.migrations.0101_clinic_discussion')
    migration.migrate_comments(apps, SimpleNamespace(connection=SimpleNamespace(alias='default')))
    migration.migrate_comments(apps, SimpleNamespace(connection=SimpleNamespace(alias='default')))
    row = ClinicComment.objects.get(legacy_opinion=opinion)
    assert row.created_at == opinion.created_at and row.body == opinion.body
    assert client(users[0]).delete(f'/api/clinic/spins/{diagnosis.pk}/opinions/').status_code == 200
    opinion.refresh_from_db()
    assert opinion.body == row.body and opinion.polarity is None


def test_reply_never_enters_email_digest(users, monkeypatch):
    from news.notification_tasks import send_notification_digests
    NotificationSettings.objects.create(user=users[0], email_digest='daily')
    Notification.objects.create(user=users[0], kind='clinic_reply', title='Odpowiedź', url='/klinika/1#dyskusja')
    mail = Mock(return_value=True)
    monkeypatch.setattr('news.account_mail.send_account_mail', mail)
    assert send_notification_digests() == 0
    mail.assert_not_called()


def test_export_includes_own_comments_reports_and_interview_ratings(subject, users):
    own = comment(subject, users[0], hidden_at=timezone.now(), hidden_reason='Test moderacji')
    other = comment(subject, users[1], body='Nie moje')
    ClinicCommentReport.objects.create(comment=other, reporter=users[0], reason='spam')
    interview = ClinicInterview.objects.create(day=timezone.localdate(), video_id='newexport01', status='approved')
    InterviewOpinion.objects.create(user=users[0], interview=interview, polarity='positive')
    data = client(users[0]).get('/api/account/export/').json()
    assert [row['body'] for row in data['clinic_comments']] == [own.body]
    assert data['clinic_comments'][0]['hidden_reason'] == 'Test moderacji'
    assert data['opinions']['interviews'][0]['interview_id'] == interview.pk
    assert data['clinic_reports'][0]['comment_id'] == other.pk
    users[0].delete()
    assert not ClinicComment.objects.filter(pk=own.pk).exists()
    assert ClinicComment.objects.filter(pk=other.pk).exists()
    assert not InterviewOpinion.objects.exists() and not ClinicCommentReport.objects.exists()


def test_csrf_required_for_session_writes(subject, users):
    reader = APIClient(enforce_csrf_checks=True)
    reader.force_login(users[0])
    assert reader.post(subject.url + 'comments/', {'body': 'Bez tokenu'}).status_code == 403
    assert reader.post(subject.url + 'opinions/', {'polarity': 'positive'}).status_code == 403


def test_screening_does_not_override_moderator_decision(subject, users):
    row = comment(subject, users[0])
    row.screening = 'pending'
    row.hidden_at = timezone.now()
    row.save()
    clinic_moderation.moderate(ClinicComment.objects.filter(pk=row.pk), users[4], False)
    clinic_moderation.finish_screening(row.pk, [])
    row.refresh_from_db()
    assert row.hidden_at and row.hidden_by_id == users[4].pk


def test_appeal_flow_once_human_review_and_notification(subject, users, monkeypatch, django_capture_on_commit_callbacks):
    sent = []
    monkeypatch.setattr(clinic_discussion, 'notify_moderators', lambda kind, pk: sent.append((kind, pk)))
    row = comment(subject, users[0], hidden_at=timezone.now(), hidden_reason='Wulgaryzmy')
    url = f'{subject.url}comments/{row.pk}/appeal/'
    visible = comment(subject, users[0], body='Widoczny')
    assert client().post(url, {}).status_code in (401, 403)
    assert client(users[1]).post(url, {}).status_code == 404  # nie cudzy komentarz
    assert client(users[0]).post(f'{subject.url}comments/{visible.pk}/appeal/', {}).status_code == 400
    with django_capture_on_commit_callbacks(execute=True):
        first = client(users[0]).post(url, {'details': 'To pomyłka'})
    assert first.status_code == 201 and first.data['status'] == 'pending'
    again = client(users[0]).post(url, {'details': 'Jeszcze raz'})
    assert again.status_code == 200 and ClinicCommentAppeal.objects.filter(comment=row).count() == 1
    assert sent == [('appeal', ClinicCommentAppeal.objects.get(comment=row).pk)]
    row.refresh_from_db()
    assert row.needs_review and row.hidden_at
    mine = client(users[0]).get(subject.url + 'comments/').data['results']
    assert next(r for r in mine if r['id'] == row.pk)['appeal'] == {'status': 'pending'}
    other = client(users[1]).get(subject.url + 'comments/').data['results']
    seen = next(r for r in other if r['id'] == row.pk)
    assert 'appeal' not in seen and seen['body'] is None
    model_admin = admin.site._registry[ClinicCommentAppeal]
    request = APIRequestFactory().post('/')
    request.user = users[4]
    model_admin.accept_appeals(request, ClinicCommentAppeal.objects.all())
    row.refresh_from_db()
    appeal = ClinicCommentAppeal.objects.get(comment=row)
    assert row.hidden_at is None and appeal.status == 'accepted' and appeal.reviewed_by_id == users[4].pk
    assert client(users[0]).post(url, {}).status_code == 200  # limit 1 na komentarz


def test_appeal_rejected_keeps_hidden_and_report_notifies(subject, users, monkeypatch, django_capture_on_commit_callbacks):
    sent = []
    monkeypatch.setattr(clinic_discussion, 'notify_moderators', lambda kind, pk: sent.append(kind))
    row = comment(subject, users[0], hidden_at=timezone.now(), hidden_reason='Spam')
    client(users[0]).post(f'{subject.url}comments/{row.pk}/appeal/', {})
    request = APIRequestFactory().post('/')
    request.user = users[4]
    admin.site._registry[ClinicCommentAppeal].reject_appeals(request, ClinicCommentAppeal.objects.all())
    row.refresh_from_db()
    assert row.hidden_at and ClinicCommentAppeal.objects.get(comment=row).status == 'rejected'
    visible = comment(subject, users[2], body='Do zgłoszenia')
    with django_capture_on_commit_callbacks(execute=True):
        client(users[1]).post(f'{subject.url}comments/{visible.pk}/report/', {'reason': 'spam'})
    assert 'report' in sent


def test_notify_moderators_message_has_no_comment_body(monkeypatch):
    calls = []
    monkeypatch.setattr('news.social_publish._mail', lambda to, subject, body, **kw: calls.append((to, subject, body)) or False)
    monkeypatch.setattr('news.raport_petli.recipient', lambda: 'zespol@example.org')
    clinic_moderation.notify_moderators('appeal', 7)
    assert calls and '#7' in calls[0][1] and 'panel admina' in calls[0][2]


def test_both_camps_have_identical_daily_message_discussion(users):
    for camp in ('government', 'opposition'):
        message = ClinicDailyMessage.objects.create(day=timezone.localdate(), camp=camp, message='Przekaz.', status='approved')
        url = f'/api/clinic/daily-messages/{message.pk}/'
        author = users[0] if camp == 'government' else users[1]
        assert client(author).post(url + 'comments/', {'body': 'Komentarz'}).status_code == 201
        assert client(users[2]).get(url + 'comments/').data['count'] == 1
        assert client(users[3]).post(url + 'opinions/', {'polarity': 'positive'}).status_code == 200
    hidden = ClinicDailyMessage.objects.create(day=timezone.localdate() - timedelta(days=1), camp='government', message='Ukryty.', status='rejected')
    assert client(users[0]).post(f'/api/clinic/daily-messages/{hidden.pk}/comments/', {'body': 'X'}).status_code == 404


def test_daily_message_comment_count_in_message_data(users):
    from news.clinic import _message_data
    message = ClinicDailyMessage.objects.create(day=timezone.localdate(), camp='opposition', message='Przekaz.', status='approved')
    assert _message_data(message)['comment_count'] == 0
    ClinicComment.objects.create(daily_message=message, author=users[0], body='A', body_hash='h')
    data = _message_data(message)
    assert data['comment_count'] == 1 and data['opinions'] == {'positive': 0, 'negative': 0}


def test_migration_0159_forward_and_back(transactional_db):
    from django.core.management import call_command
    from django.db import connection

    def columns():
        return {c.name for c in connection.introspection.get_table_description(connection.cursor(), 'news_cliniccomment')}
    call_command('migrate', 'news', '0158_poczta_wychodzaca', verbosity=0)
    assert 'daily_message_id' not in columns()
    call_command('migrate', 'news', verbosity=0)
    assert 'daily_message_id' in columns()
