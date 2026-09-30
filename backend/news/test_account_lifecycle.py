from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.test import APIClient

from news.account_models import AccountIdentity, PersonalContextThread, ArticleFavorite
from news.account_lifecycle import send_verification, send_password_reset
from news.models import Article, Source

pytestmark = pytest.mark.django_db
PASSWORD = 'Str0ng~unique~zxcv!'


@pytest.fixture(autouse=True)
def configured(settings):
    settings.ACCOUNTS_ENABLED = True
    settings.THREADS_ENABLED = True
    settings.ACCOUNT_PUBLIC_URL = 'https://portal.example'
    cache.clear()


@pytest.fixture
def user():
    user = get_user_model().objects.create_user('reader', email='reader@example.org', password=PASSWORD)
    AccountIdentity.objects.create(user=user, email=user.email)
    return user


def registration(**extra):
    return {'username': 'newreader', 'email': 'new@example.org', 'password': PASSWORD,
            'accepted_terms': True, 'accepted_privacy': True, **extra}


def test_register_required_email_consents_and_no_privileges():
    client = APIClient()
    with patch('news.account_lifecycle.send_account_verification.apply_async') as queued:
        response = client.post('/api/account/register/', registration(is_staff=True, is_superuser=True), format='json')
    assert response.status_code == 201
    assert response.data['authenticated'] is False
    user = get_user_model().objects.get(username='newreader')
    assert user.check_password(PASSWORD) and not user.is_staff and not user.is_superuser
    identity = user.account_identity
    assert not identity.email_verified and identity.accepted_at
    assert identity.accepted_terms_version and identity.accepted_privacy_version
    queued.assert_called_once_with(args=['new@example.org'], retry=False)


@pytest.mark.parametrize('field,value', [('email', ''), ('accepted_terms', False), ('accepted_privacy', False)])
def test_registration_rejects_missing_requirements(field, value):
    response = APIClient().post('/api/account/register/', registration(**{field: value}), format='json')
    assert response.status_code == 400 and field in response.data


def test_registration_email_enumeration(user):
    client = APIClient()
    with patch('news.account_lifecycle.send_account_verification.apply_async') as queued:
        known = client.post('/api/account/register/', registration(email=user.email), format='json')
        unknown = client.post('/api/account/register/', registration(email='unused@example.org'), format='json')
    assert known.status_code == unknown.status_code == 201
    assert {k: v for k, v in known.data.items() if k != 'csrfToken'} == {k: v for k, v in unknown.data.items() if k != 'csrfToken'}
    assert queued.call_count == 2
    assert get_user_model().objects.filter(email=user.email).count() == 1


def verification_token(user):
    with patch('news.account_lifecycle.send_account_mail') as mail:
        send_verification(user)
    body = mail.call_args.args[2]
    link = body.split('https://', 1)[1].split()[0]
    return parse_qs(urlparse('https://' + link).query)['token'][0]


def test_verification_single_use_signed_and_private_access(user):
    client = APIClient()
    client.force_authenticate(user)
    # Unverified accounts still have private storage.
    response = client.post('/api/account/context-threads/', {'title': 'Prywatna'}, format='json')
    assert response.status_code == 201
    token = verification_token(user)
    assert client.post('/api/account/verify-email/', {'token': token + 'bad'}, format='json').status_code == 400
    assert client.post('/api/account/verify-email/', {'token': token}, format='json').status_code == 200
    assert client.post('/api/account/verify-email/', {'token': token}, format='json').status_code == 400
    user.account_identity.refresh_from_db()
    assert user.account_identity.email_verified


def test_verify_expires_after_48_hours(user):
    with patch('django.core.signing.time.time', return_value=1000000):
        token = verification_token(user)
    with patch('django.core.signing.time.time', return_value=1000000 + 48 * 3600 + 1):
        assert APIClient().post('/api/account/verify-email/', {'token': token}, format='json').status_code == 400


def test_resend_requires_session_and_limits(user):
    client = APIClient()
    assert client.post('/api/account/verify-email/resend/', {}, format='json').status_code == 403
    client.force_authenticate(user)
    with patch('news.account_lifecycle.send_account_verification.apply_async') as queued:
        assert client.post('/api/account/verify-email/resend/', {}, format='json').status_code == 200
        assert client.post('/api/account/verify-email/resend/', {}, format='json').status_code == 429
    queued.assert_called_once()


def test_login_with_email_or_username(user):
    client = APIClient()
    for name in ('READER', 'READER@EXAMPLE.ORG'):
        response = client.post('/api/account/login/', {'username': name, 'password': PASSWORD}, format='json')
        assert response.status_code == 200
        assert response.data['user']['email'] == user.email
        assert not response.data['user']['email_verified']


def test_missing_email_never_authenticates_a_placeholder_user():
    get_user_model().objects.create_user('__no_such_email__', password=PASSWORD)
    response = APIClient().post('/api/account/login/', {'username': 'absent@example.org', 'password': PASSWORD}, format='json')
    assert response.status_code == 403


def test_reset_does_not_reveal_email_and_queues_same_way(user):
    client = APIClient()
    with patch('news.account_lifecycle.send_password_reset.apply_async') as queued:
        known = client.post('/api/account/password-reset/', {'email': user.email}, format='json')
        unknown = client.post('/api/account/password-reset/', {'email': 'absent@example.org'}, format='json')
    assert known.status_code == unknown.status_code == 200
    assert known.data == unknown.data and queued.call_count == 2
    with patch('news.account_lifecycle.send_password_reset.apply_async', side_effect=RuntimeError('broker down')):
        assert client.post('/api/account/password-reset/', {'email': 'third@example.org'}, format='json').data == known.data


def reset_values(user):
    return {'uid': urlsafe_base64_encode(force_bytes(user.pk)), 'token': default_token_generator.make_token(user),
            'password': 'An0ther~strong~zxcv!'}


def test_reset_token_single_use_invalidates_old_session(user):
    existing = APIClient()
    existing.force_login(user)
    client = APIClient()
    data = reset_values(user)
    assert client.post('/api/account/password-reset/confirm/', data, format='json').status_code == 200
    assert client.post('/api/account/password-reset/confirm/', data, format='json').status_code == 400
    assert existing.get('/api/account/me/').data['authenticated'] is False
    user.refresh_from_db()
    assert user.check_password(data['password'])


def test_reset_one_hour_expiry_and_validation(user):
    now = datetime(2026, 9, 30)
    with patch.object(default_token_generator, '_now', return_value=now):
        data = reset_values(user)
    with patch.object(default_token_generator, '_now', return_value=now + timedelta(seconds=3601)):
        assert APIClient().post('/api/account/password-reset/confirm/', data, format='json').status_code == 400
    data = reset_values(user)
    data['password'] = '123'
    assert 'password' in APIClient().post('/api/account/password-reset/confirm/', data, format='json').data


def test_google_only_account_can_set_password(user):
    user.set_unusable_password()
    user.save()
    with patch('news.account_lifecycle.send_account_mail') as mail:
        send_password_reset(user.email)
    assert '/konto/nowe-haslo?' in mail.call_args.args[2]
    assert APIClient().post('/api/account/password-reset/confirm/', reset_values(user), format='json').status_code == 200


def test_publication_blocked_across_opinion_endpoints(user):
    client = APIClient()
    client.force_authenticate(user)
    for url in ('/api/articles/1/opinions/', '/api/threads/sample/opinions/', '/api/clinic/spins/1/opinions/', '/api/community/threads/1/opinions/'):
        # Verification happens before looking up an object.
        response = client.post(url, {'polarity': 'positive'}, format='json')
        assert response.status_code == 403, (url, response.status_code)


def test_public_thread_requires_verification_but_private_save_works(user, monkeypatch):
    monkeypatch.setenv('THREADS_ENABLED', 'true')
    source = Source.objects.create(name='Source', url='https://example.org')
    articles = [Article.objects.create(source=source, title=f'Article {i}', url=f'https://example.org/{i}') for i in range(2)]
    client = APIClient()
    client.force_authenticate(user)
    payload = {'title': 'Moja nitka', 'article_ids': [a.pk for a in articles]}
    private = client.post('/api/account/context-threads/', payload, format='json')
    assert private.status_code == 201
    url = f'/api/account/context-threads/{private.data["id"]}/'
    assert client.patch(url, {'is_public': True}, format='json').status_code == 403
    user.account_identity.email_verified = True
    user.account_identity.save()
    assert client.patch(url, {'is_public': True}, format='json').status_code == 200


def test_export_is_owner_scoped_and_delete_cascades(user):
    other = get_user_model().objects.create_user('other', email='other@example.org')
    private = PersonalContextThread.objects.create(owner=user, title='Private')
    public = PersonalContextThread.objects.create(owner=user, title='Public', is_public=True)
    other_thread = PersonalContextThread.objects.create(owner=other, title='Other private')
    source = Source.objects.create(name='Source', url='https://example.org')
    article = Article.objects.create(source=source, title='Article', url='https://example.org/a')
    ArticleFavorite.objects.create(user=user, article=article)
    client = APIClient()
    assert client.get('/api/account/export/').status_code == 403
    client.force_login(user)
    exported = client.get('/api/account/export/')
    assert exported.status_code == 200 and 'attachment' in exported['Content-Disposition']
    data = exported.json()
    assert {t['id'] for t in data['threads']} == {private.pk, public.pk}
    assert 'password' not in data['account']
    assert data['favorites']['articles'][0]['article_id'] == article.pk
    assert client.post('/api/account/delete/', {'password': 'bad', 'confirm': 'USUŃ'}, format='json').status_code == 400
    assert client.post('/api/account/delete/', {'password': PASSWORD, 'confirm': 'no'}, format='json').status_code == 400
    assert client.post('/api/account/delete/', {'password': PASSWORD, 'confirm': 'USUŃ'}, format='json').status_code == 200
    assert not get_user_model().objects.filter(pk=user.pk).exists()
    assert not PersonalContextThread.objects.filter(pk__in=[private.pk, public.pk]).exists()
    assert PersonalContextThread.objects.filter(pk=other_thread.pk).exists()
    assert not AccountIdentity.objects.filter(user_id=user.pk).exists()


def test_feature_off_and_csrf(settings, user):
    settings.ACCOUNTS_ENABLED = False
    client = APIClient()
    for url in ('register', 'password-reset'):  # logowanie zostaje otwarte dla zespołu i dziennikarzy
        assert client.post(f'/api/account/{url}/', {}, format='json').status_code == 404
    settings.ACCOUNTS_ENABLED = True
    client = APIClient(enforce_csrf_checks=True)
    assert client.post('/api/account/password-reset/', {'email': user.email}, format='json').status_code == 403
    assert client.post('/api/account/verify-email/', {'token': 'anything'}, format='json').status_code == 403


def test_email_change_requires_password_and_reverification(user):
    user.account_identity.email_verified = True
    user.account_identity.save()
    client = APIClient()
    client.force_authenticate(user)
    assert client.patch('/api/account/me/', {'email': 'changed@example.org'}, format='json').status_code == 400
    with patch('news.account_lifecycle.send_account_verification.apply_async'):
        response = client.patch('/api/account/me/', {'email': 'changed@example.org', 'password': PASSWORD}, format='json')
    assert response.status_code == 200
    assert response.data['user']['email'] == 'changed@example.org'
    assert response.data['user']['email_verified'] is False


def test_legacy_account_can_supply_email_and_consents():
    user = get_user_model().objects.create_user('legacy', password=PASSWORD)
    client = APIClient()
    client.force_authenticate(user)
    values = {'email': 'legacy@example.org', 'password': PASSWORD, 'accepted_terms': True, 'accepted_privacy': True}
    with patch('news.account_lifecycle.send_account_verification.apply_async') as queued:
        response = client.patch('/api/account/me/', values, format='json')
    assert response.status_code == 200 and response.data['csrfToken']
    identity = AccountIdentity.objects.get(user=user)
    assert identity.email == values['email'] and identity.accepted_at and not identity.email_verified
    queued.assert_called_once()


def test_legacy_existing_email_also_gets_verification():
    user = get_user_model().objects.create_user('legacy', email='legacy@example.org', password=PASSWORD)
    client = APIClient()
    client.force_authenticate(user)
    with patch('news.account_lifecycle.send_account_verification.apply_async') as queued:
        response = client.patch('/api/account/me/', {'email': user.email, 'password': PASSWORD,
            'accepted_terms': True, 'accepted_privacy': True}, format='json')
    assert response.status_code == 200
    queued.assert_called_once()


def test_mail_uses_existing_smtp_configuration(settings):
    from news.account_mail import send_account_mail
    settings.SOURCE_MAIL_SMTP_ENABLED = True
    settings.SOURCE_MAIL_SMTP_HOST = 'smtp.example.org'
    settings.SOURCE_MAIL_SMTP_PORT = 465
    settings.SOURCE_MAIL_SMTP_USERNAME = 'account'
    settings.SOURCE_MAIL_SMTP_PASSWORD = 'fixture-secret'
    settings.SOURCE_MAIL_SMTP_FROM = 'accounts@example.org'
    with patch('news.account_mail.smtplib.SMTP_SSL') as smtp:
        assert send_account_mail('reader@example.org', 'Subject', 'Body')
        smtp.return_value.__enter__.return_value.login.assert_called_once_with('account', 'fixture-secret')
        smtp.return_value.__enter__.return_value.send_message.assert_called_once()
