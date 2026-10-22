from io import StringIO
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.management import call_command, CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from news import social_assistant, social_publish
from news.clinic_models import SocialPost, SpinDiagnosis
from news.social_models import SocialAssistantUsage, SocialMaterial, SocialTask
from news.test_clinic import account, post

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolation(monkeypatch, tmp_path):
    cache.clear()
    monkeypatch.setenv('SOCIAL_MEDIA_DIR', str(tmp_path))
    yield
    cache.clear()


@pytest.fixture
def social_user():
    user = get_user_model().objects.create_user('social-test', email='social@example.com', password='Test-social-1234')
    user.groups.add(Group.objects.get_or_create(name='social')[0])
    return user


@pytest.fixture
def client(social_user):
    client = APIClient()
    client.force_authenticate(social_user)
    return client


@pytest.fixture
def material():
    diagnosis = SpinDiagnosis.objects.create(post=post(account()), status='approved', verdict='spin', intensity=75,
        headline='Gotowy materiał', x_thread=['Zapisana synteza.'])
    row = SocialMaterial.objects.create(diagnosis=diagnosis, caption='Dokładny opis z maila', link=f'https://spin.clinic/klinika/{diagnosis.pk}')
    (social_publish.video_dir() / social_publish.video_name(diagnosis.pk)).write_bytes(b'video')
    return row


def test_permissions_and_login(social_user, settings):
    settings.ACCOUNTS_ENABLED = False
    anonymous = APIClient()
    for path in ['/api/social/queue/', '/api/social/tasks/', '/api/social/published/']:
        assert anonymous.get(path).status_code in (401, 403)
    response = anonymous.post('/api/account/login/', {'username': social_user.email, 'password': 'Test-social-1234'})
    assert response.status_code == 200 and response.data['user']['is_social']
    assert anonymous.get('/api/social/queue/').status_code == 200
    assert not social_user.is_staff
    reader = get_user_model().objects.create_user('reader')
    anonymous.force_authenticate(reader)
    assert anonymous.get('/api/social/queue/').status_code == 403


def test_all_staff_and_admin_routes_deny_social(client, social_user):
    from django.urls import URLPattern, URLResolver
    from news.urls import urlpatterns
    import re
    def paths(patterns, prefix=''):
        for pattern in patterns:
            route = prefix + str(pattern.pattern)
            if isinstance(pattern, URLResolver):
                yield from paths(pattern.url_patterns, route)
            elif isinstance(pattern, URLPattern) and route.startswith(('staff/', 'admin/')):
                if '(?P<format>' in route:
                    continue
                route = re.sub(r'\(\?P<[^>]+>[^)]+\)', '1', route).replace('^', '').replace('$', '')
                yield '/api/' + re.sub(r'<[^>]+>', '1', route)
    for path in paths(urlpatterns):
        for method in ('get', 'post', 'patch'):
            assert getattr(client, method)(path).status_code in (401, 403, 405), (path, method)
    client.force_login(social_user)
    assert client.get('/admin/').status_code == 302
    assert client.get('/api/editor/threads/').status_code == 403


def test_staff_can_access_both(client, social_user, monkeypatch):
    social_user.is_staff = True
    social_user.save()
    monkeypatch.setattr('news.admin_status.snapshot', lambda now: {'sections': []})
    assert client.get('/api/social/queue/').status_code == 200
    assert client.get('/api/admin/status/').status_code == 200
    assert client.get('/api/staff/social/tasks/').status_code == 200


def test_queue_ready_only_and_publication(client, material, monkeypatch):
    monkeypatch.setattr('news.clinic.ensure_x_thread', Mock(side_effect=AssertionError('GET cannot use AI')))
    data = client.get('/api/social/queue/').data['items']
    assert len(data) == 1 and data[0]['caption'] == material.caption
    assert client.get(data[0]['video']).status_code == 200
    d = material.diagnosis
    pending = SpinDiagnosis.objects.create(post=post(d.post.account, post_id='other'), status='queued')
    assert all(item['id'] != pending.pk for item in client.get('/api/social/queue/').data['items'])
    url = f'/api/social/materials/{d.pk}/'
    assert client.post(url, {'action': 'tiktok', 'url': 'https://evil.example/post'}).status_code == 400
    assert client.post(url, {'action': 'tiktok', 'url': 'https://www.tiktok.com/@spin/video/123'}).status_code == 200
    first = SocialPost.objects.get(diagnosis=d, platform='tiktok')
    assert client.post(url, {'action': 'tiktok', 'url': first.url}).status_code == 200
    assert SocialPost.objects.filter(diagnosis=d, platform='tiktok').count() == 1
    assert client.get('/api/social/queue/').data['items'][0]['posts'][0]['url'] == first.url
    assert client.post(url, {'action': 'shorts', 'url': 'https://www.youtube.com/shorts/123'}).status_code == 200
    assert client.get('/api/social/queue/').data['items'] == []
    assert len(client.get('/api/social/published/').data['items']) == 2
    first.refresh_from_db()
    assert first.posted_at == client.get('/api/social/published/').data['items'][1]['posted_at']


def test_missing_file_not_ready(client, material):
    (social_publish.video_dir() / social_publish.video_name(material.diagnosis_id)).unlink()
    assert client.get('/api/social/queue/').data['items'] == []
    assert client.post(f'/api/social/materials/{material.diagnosis_id}/', {'action': 'shorts', 'url': 'https://youtu.be/123'}).status_code == 409


def test_pipeline_saves_exact_material_even_when_mail_fails(client, material, monkeypatch):
    d = material.diagnosis
    material.delete()
    monkeypatch.setattr(social_publish, 'channels', lambda: ['manual'])
    monkeypatch.setattr(social_publish, 'candidates', lambda *a: [d])
    monkeypatch.setattr(social_publish, 'texts', lambda *a, **kw: {'instagram': 'Opis do wysłania', 'link': 'https://spin.clinic/klinika/1'})
    monkeypatch.setattr(social_publish, 'post_manual', Mock(side_effect=RuntimeError('mail_failed')))
    monkeypatch.setattr(social_publish, 'alert', Mock())
    assert social_publish.run()['results'][0]['posted'] is False
    assert client.get('/api/social/queue/').data['items'][0]['caption'] == 'Opis do wysłania'


def test_legacy_material_reuses_saved_synthesis_without_models(client, material, monkeypatch):
    material.caption = ''
    material.save()
    monkeypatch.setattr('news.clinic.detail_data', lambda d: {'id': d.pk, 'x_thread': d.x_thread})
    monkeypatch.setattr(social_publish, 'texts_from_data', lambda d: {'instagram': d['x_thread'][0], 'link': 'https://spin.clinic/klinika/1'})
    monkeypatch.setattr('news.clinic.ensure_x_thread', Mock(side_effect=AssertionError('No generation')))
    assert client.get('/api/social/queue/').data['items'][0]['caption'] == 'Zapisana synteza.'


def test_skip_and_removal_notice_until_confirmation(client, material, monkeypatch):
    d = material.diagnosis
    url = f'/api/social/materials/{d.pk}/'
    SocialPost.objects.create(diagnosis=d, platform='manual')
    SocialPost.objects.create(diagnosis=d, platform='tiktok', url='https://www.tiktok.com/@spin/video/123')
    assert client.post(url, {'action': 'removed'}).status_code == 400
    assert client.post(url, {'action': 'skip'}).status_code == 200
    assert client.get('/api/social/queue/').data['items'] == []
    d.post.available = False
    d.post.save()
    monkeypatch.setattr(social_publish, '_mail', Mock(return_value=True))
    social_publish.unpublish_deleted(d)
    assert not d.social_posts.filter(deleted_at__isnull=False).exists()
    item = client.get('/api/social/queue/').data['items'][0]
    assert item['remove_required'] and 'caption' not in item and 'video' not in item
    # Direct view check avoids Django 5.1 template-copy incompatibility with Python 3.14 on 404.
    from django.http import Http404
    with pytest.raises(Http404):
        social_publish.serve_video(None, social_publish.video_name(d.pk))
    assert client.post(url, {'action': 'shorts', 'url': 'https://youtu.be/123'}).status_code == 409
    assert client.post(url, {'action': 'removed'}).status_code == 200
    assert client.get('/api/social/queue/').data['items'] == []
    assert d.social_posts.filter(deleted_at__isnull=False).count() == 2


def test_question_answer_and_private_inbox(client, social_user, monkeypatch):
    ask = Mock(return_value=({'answer': 'Pobierz film i skopiuj gotowy opis.'}, 'free'))
    monkeypatch.setattr(social_assistant, 'ask_role', ask)
    response = client.post('/api/social/tasks/', {'kind': 'question', 'content': 'Jak publikować?', 'answered_by': 'owner'})
    assert response.status_code == 201
    assert response.data['answer'].startswith('Pobierz') and response.data['answered_by'] == 'assistant'
    assert response.data['status'] == 'done'
    other = get_user_model().objects.create_user('other-social')
    other.groups.add(Group.objects.get(name='social'))
    client.force_authenticate(other)
    assert client.get('/api/social/tasks/').data['items'] == []
    assert client.patch(f"/api/staff/social/tasks/{response.data['id']}/", {'answer': 'Nie'}).status_code == 403


def test_assistant_limit_including_fallback_and_paid_guard(client, monkeypatch):
    from news import clinic_council, council_registry
    from news.clinic_ai import ClinicAIError
    monkeypatch.setenv('SOCIAL_ASSISTANT_DAILY_CALLS', '2')
    members = [('gemini', 'gemini-paid'), ('openrouter', 'paid'), ('groq', 'free-one'), ('nim', 'free-two')]
    monkeypatch.setattr(clinic_council, '_members', lambda *a: members)
    monkeypatch.setattr(council_registry, 'available', lambda m: True)
    calls = []
    def ask(member, *a):
        if not council_registry.reserve(member):
            raise ClinicAIError('limit')
        calls.append(member)
        if member[0] == 'groq':
            raise ClinicAIError('unavailable')
        return {'answer': 'Gotowa odpowiedź'}
    monkeypatch.setattr(clinic_council, 'ask', ask)
    response = client.post('/api/social/tasks/', {'kind': 'question', 'content': 'Pomoc'})
    assert response.data['answer'] == 'Gotowa odpowiedź'
    response = client.post('/api/social/tasks/', {'kind': 'question', 'content': 'Jeszcze raz'})
    assert response.data['answer'] == 'Odpowiem później' and response.data['status'] == 'new'
    assert calls == members[2:] and SocialAssistantUsage.objects.get().calls == 2
    assert council_registry.reservation_guard.get() is None


@pytest.mark.parametrize('limit', ['0', '-1', 'invalid'])
def test_assistant_disabled_limit(monkeypatch, limit):
    monkeypatch.setenv('SOCIAL_ASSISTANT_DAILY_CALLS', limit)
    assert not social_assistant.reserve(('groq', 'free'), 1)


def test_model_unavailable_keeps_question_for_staff(client, monkeypatch):
    from news.clinic_ai import ClinicAIError
    monkeypatch.setattr(social_assistant, 'ask_role', Mock(side_effect=ClinicAIError('unavailable')))
    response = client.post('/api/social/tasks/', {'kind': 'question', 'content': 'Pomoc'})
    assert response.data['answer'] == 'Odpowiem później'
    assert response.data['answered_by'] == 'assistant' and response.data['status'] == 'new'


def test_task_visible_for_staff_and_reply(client, social_user):
    response = client.post('/api/social/tasks/', {'kind': 'task', 'content': 'Proszę o nowy film.'})
    assert response.status_code == 201 and not response.data['answer']
    staff = get_user_model().objects.create_user('owner', is_staff=True)
    client.force_authenticate(staff)
    data = client.get('/api/staff/social/tasks/').data
    assert data['new_count'] == 1 and data['items'][0]['content'] == 'Proszę o nowy film.'
    from news.social_api import panel_section
    assert panel_section()['metrics'] == [{'label': 'Nowe', 'value': 1}]
    path = f"/api/staff/social/tasks/{response.data['id']}/"
    assert client.get(path).status_code == 405
    assert client.patch('/api/staff/social/tasks/', {'status': 'done'}).status_code == 405
    assert client.patch(path, {'status': 'progress'}).status_code == 200
    assert client.patch(path, {'status': 'done', 'answer': 'Gotowe.', 'answered_by': 'claude'}).status_code == 200
    client.force_authenticate(social_user)
    task = client.get('/api/social/tasks/').data['items'][0]
    assert task['answer'] == 'Gotowe.' and task['answered_by'] == 'claude' and task['answered_at']


def test_command_and_one_use_password_link(monkeypatch, settings):
    settings.ACCOUNTS_ENABLED = False
    mail = Mock(return_value=False)
    monkeypatch.setattr('news.management.commands.create_social_manager.send_account_mail', mail)
    output = StringIO()
    call_command('create_social_manager', email='tata@example.com', name='Tata', stdout=output)
    user = get_user_model().objects.get(email='tata@example.com')
    assert not user.has_usable_password() and not user.is_staff and not user.is_superuser
    assert user.groups.filter(name='social').exists()
    query = parse_qs(urlsplit(output.getvalue().splitlines()[-1]).query)
    payload = {key: value[0] for key, value in query.items()}
    payload['password'] = 'Nowe-silne-haslo-1234!'
    client = APIClient()
    assert client.post('/api/social/password/confirm/', payload).status_code == 200
    assert client.post('/api/social/password/confirm/', payload).status_code == 400
    user.refresh_from_db()
    assert user.check_password(payload['password'])
    with pytest.raises(CommandError):
        call_command('create_social_manager', email='tata@example.com', name='Tata')


def test_command_emails_invitation_without_printing_token(monkeypatch):
    mail = Mock(return_value=True)
    monkeypatch.setattr('news.management.commands.create_social_manager.send_account_mail', mail)
    output = StringIO()
    call_command('create_social_manager', email='invited@example.com', name='Tata', stdout=output)
    assert mail.call_args.args[0] == 'invited@example.com'
    assert '/panel/social/haslo?' in mail.call_args.args[2]
    assert 'token=' not in output.getvalue()


def test_password_setup_cannot_reset_non_social_user(settings):
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode
    user = get_user_model().objects.create_user('ordinary', password='Original-123')
    payload = {'uid': urlsafe_base64_encode(force_bytes(user.pk)), 'token': default_token_generator.make_token(user), 'password': 'Changed-123!'}
    assert APIClient().post('/api/social/password/confirm/', payload).status_code == 400


def test_published_last_fifty(client, material):
    d = material.diagnosis
    for number in range(51):
        diagnosis = SpinDiagnosis.objects.create(post=post(d.post.account, post_id=f'published-{number}'), status='approved')
        SocialPost.objects.create(diagnosis=diagnosis, platform='shorts', url=f'https://youtu.be/{number}')
    data = client.get('/api/social/published/').data['items']
    assert len(data) == 50 and data[0]['url'] == 'https://youtu.be/50' and data[-1]['url'] == 'https://youtu.be/1'


def test_csrf_and_throttle(social_user, monkeypatch):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(social_user)
    assert client.post('/api/social/tasks/', {'kind': 'task', 'content': 'CSRF'}).status_code == 403
    client = APIClient()
    client.force_authenticate(social_user)
    monkeypatch.setattr('news.social_api.SocialWriteThrottle.rate', '1/hour')
    assert client.post('/api/social/tasks/', {'kind': 'task', 'content': 'Raz'}).status_code == 201
    assert client.post('/api/social/tasks/', {'kind': 'task', 'content': 'Dwa'}).status_code == 429


def test_migration_group_and_legacy_backfill(material):
    import importlib
    from django.apps import apps
    from django.db import connection
    from types import SimpleNamespace
    SocialPost.objects.create(diagnosis=material.diagnosis, platform='manual')
    material.delete()
    importlib.import_module('news.migrations.0108_social_manager').seed_social(apps, SimpleNamespace(connection=connection))
    assert Group.objects.filter(name='social').exists()
    assert SocialMaterial.objects.count() == 1
