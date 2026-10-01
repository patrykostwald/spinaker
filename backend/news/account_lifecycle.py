"""Email verification, recovery and owner-only account lifecycle."""
import secrets
from urllib.parse import urlencode

from celery import shared_task
from django.conf import settings
from news.features import accounts_enabled
from news.preview import mail_preview_kwargs, valid_preview
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from news.account_mail import send_account_mail
from news.account_models import AccountIdentity
from news.account_security import AccountEnabled
from news.accounts import AccountIPThrottle, AccountWriteThrottle, user_data

VERIFY_SALT = 'news.account.verify.v1'


@shared_task(ignore_result=True)
def send_account_verification(email, preview_grant=None):
    if not (settings.ACCOUNTS_ENABLED or valid_preview(preview_grant)):
        return
    identity = AccountIdentity.objects.select_related('user').filter(email=email, email_verified=False).first()
    if identity and cache.add(f'account-verification-delivery:{identity.user_id}', True, 300):
        send_verification(identity.user)


def queue_verification(email):
    try:
        send_account_verification.apply_async(args=[email], retry=False, **mail_preview_kwargs())
    except Exception:
        import logging
        logging.getLogger(__name__).warning('Account verification queue unavailable')


def send_verification(user):
    with transaction.atomic():
        identity = AccountIdentity.objects.select_for_update().get(user=user)
        if identity.email_verified:
            return
        # A stable nonce keeps delayed mail valid after concurrent resends.
        if not identity.verification_nonce:
            identity.verification_nonce = secrets.token_urlsafe(32)
            identity.save(update_fields=['verification_nonce'])
        token = signing.dumps({'id': user.pk, 'email': identity.email,
                               'nonce': identity.verification_nonce}, salt=VERIFY_SALT)
    url = settings.ACCOUNT_PUBLIC_URL + '/konto/potwierdz?' + urlencode({'token': token})
    send_account_mail(identity.email, 'Potwierdź e-mail w spin.clinic',
                      f'Potwierdź swój e-mail: {url}\n\nLink działa przez 48 godzin.\nOperator: iapply sp. z o.o.')


class VerifyInput(serializers.Serializer):
    token = serializers.CharField(max_length=2048)


@method_decorator(csrf_protect, name='dispatch')
class VerifyEmailView(APIView):
    permission_classes = [AccountEnabled, AllowAny]
    throttle_classes = [AccountIPThrottle]

    def post(self, request):
        serializer = VerifyInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
        try:
            data = signing.loads(token, salt=VERIFY_SALT, max_age=48 * 3600)
            with transaction.atomic():
                identity = AccountIdentity.objects.select_for_update().get(user_id=data['id'], email=data['email'])
                if identity.email_verified or not identity.verification_nonce or not secrets.compare_digest(identity.verification_nonce, data['nonce']):
                    raise ValueError()
                identity.email_verified = True
                identity.verification_nonce = ''
                identity.save(update_fields=['email_verified', 'verification_nonce'])
        except (signing.BadSignature, AccountIdentity.DoesNotExist, KeyError, TypeError, ValueError):
            return Response({'token': ['Link jest nieprawidłowy lub wygasł.']}, status=400)
        return Response({'detail': 'E-mail potwierdzony. Możesz już publikować.'})


class ResendVerificationView(APIView):
    permission_classes = [AccountEnabled, IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]

    def post(self, request):
        if not cache.add(f'account-verify-resend:{request.user.pk}', True, 300):
            return Response({'detail': 'Odczekaj 5 minut przed kolejną wysyłką.'}, status=429)
        identity = getattr(request.user, 'account_identity', None)
        if identity:
            queue_verification(identity.email)
        return Response({'detail': 'Sprawdź pocztę i folder spam.'})


class ResetInput(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


@shared_task(ignore_result=True)
def send_password_reset(email, preview_grant=None):
    if not (settings.ACCOUNTS_ENABLED or valid_preview(preview_grant)):
        return
    # The same task is queued for every valid address. No existence check in HTTP.
    users = list(get_user_model().objects.filter(email__iexact=email, is_active=True)[:2])
    if len(users) != 1:
        return
    user = users[0]
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    url = settings.ACCOUNT_PUBLIC_URL + '/konto/nowe-haslo?' + urlencode({'uid': uid, 'token': token})
    send_account_mail(user.email, 'Nowe hasło do spin.clinic',
                      f'Ustaw nowe hasło: {url}\n\nLink działa przez godzinę. Jeśli to nie Twoja prośba, pomiń ten e-mail.')


@method_decorator(csrf_protect, name='dispatch')
class PasswordResetView(APIView):
    permission_classes = [AccountEnabled, AllowAny]
    throttle_classes = [AccountIPThrottle]

    def post(self, request):
        data = ResetInput(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data['email'].strip().lower()
        from hashlib import sha256
        if cache.add('account-reset:' + sha256(email.encode()).hexdigest(), True, 300):
            try:
                send_password_reset.apply_async(args=[email], retry=False, **mail_preview_kwargs())
            except Exception:
                # Broker failure must not become an account-existence oracle.
                import logging
                logging.getLogger(__name__).warning('Password recovery queue unavailable')
        return Response({'detail': 'Jeśli konto istnieje, wyślemy link do ustawienia nowego hasła.'})


class ResetConfirmInput(serializers.Serializer):
    uid = serializers.CharField(max_length=128)
    token = serializers.CharField(max_length=256)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


@method_decorator(csrf_protect, name='dispatch')
class PasswordResetConfirmView(APIView):
    permission_classes = [AccountEnabled, AllowAny]
    throttle_classes = [AccountIPThrottle]

    def post(self, request):
        data = ResetConfirmInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        try:
            uid = urlsafe_base64_decode(values['uid']).decode()
            with transaction.atomic():
                user = get_user_model().objects.select_for_update().get(pk=uid, is_active=True)
                if not default_token_generator.check_token(user, values['token']):
                    raise ValueError()
                try:
                    validate_password(values['password'], user)
                except ValidationError as exc:
                    return Response({'password': exc.messages}, status=400)
                user.set_password(values['password'])
                user.save(update_fields=['password'])
        except (ValueError, TypeError, OverflowError, UnicodeDecodeError, get_user_model().DoesNotExist):
            return Response({'token': ['Link jest nieprawidłowy lub wygasł. Poproś o nowy.']}, status=400)
        return Response({'detail': 'Hasło zmienione. Możesz się zalogować.'})


class AccountUpdateInput(serializers.Serializer):
    email = serializers.EmailField(max_length=254, required=False)
    password = serializers.CharField(max_length=256, trim_whitespace=False, required=False)
    accepted_terms = serializers.BooleanField(required=False)
    accepted_privacy = serializers.BooleanField(required=False)


def update_account(request):
    data = AccountUpdateInput(data=request.data)
    data.is_valid(raise_exception=True)
    values = data.validated_data
    user = request.user
    email = values.get('email', user.email).strip().lower()
    changing = email != user.email.lower()
    identity = getattr(user, 'account_identity', None)
    if (changing or not identity) and not user.check_password(values.get('password', '')):
        return Response({'password': ['Podaj aktualne hasło.']}, status=400)
    if not identity and not (values.get('accepted_terms') and values.get('accepted_privacy')):
        return Response({'accepted_terms': ['Zaakceptuj zasady i politykę prywatności.']}, status=400)
    if not identity and not email:
        return Response({'email': ['Podaj e-mail.']}, status=400)
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=user.pk)
            if changing and get_user_model().objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                return Response({'email': ['Nie można zapisać tego adresu.']}, status=400)
            identity, created = AccountIdentity.objects.get_or_create(user=user, defaults={'email': email})
            if changing:
                identity.email = email
                identity.email_verified = False
                identity.verification_nonce = ''
                user.email = email
                user.save(update_fields=['email'])
            if values.get('accepted_terms') and values.get('accepted_privacy'):
                identity.accepted_terms_version = settings.ACCOUNT_TERMS_VERSION
                identity.accepted_privacy_version = settings.ACCOUNT_PRIVACY_VERSION
                identity.accepted_at = timezone.now()
            identity.save()
    except IntegrityError:
        return Response({'email': ['Nie można zapisać tego adresu.']}, status=400)
    if changing or created:
        queue_verification(email)
    user = get_user_model().objects.get(pk=user.pk)
    return Response({'authenticated': True, 'user': user_data(user), 'csrfToken': get_token(request),
                     'accounts_enabled': accounts_enabled(),
                     'google_enabled': bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)})


class AccountExportView(APIView):
    permission_classes = [AccountEnabled, IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]

    def get(self, request):
        user = request.user
        def rows(relation, *fields):
            return list(getattr(user, relation).values(*fields))
        identity = getattr(user, 'account_identity', None)
        threads = rows('personal_context_threads', 'id', 'title', 'description', 'query', 'categories', 'topics',
                       'is_public', 'created_at', 'updated_at', 'published_at')
        for thread in threads:
            value = user.personal_context_threads.get(pk=thread['id'])
            thread['source_ids'] = list(value.sources.values_list('pk', flat=True))
            thread['items'] = list(value.items.values('article_id', 'link__title', 'link__canonical_url', 'link__domain', 'note', 'position'))
        from news.notification_api import follow_data
        from news.notification_models import Follow
        response = JsonResponse({
            'account': {**user_data(user), 'date_joined': user.date_joined, 'last_login': user.last_login,
                        'first_name': user.first_name, 'last_name': user.last_name},
            'consents': {'accepted_terms_version': identity.accepted_terms_version if identity else '',
                         'accepted_privacy_version': identity.accepted_privacy_version if identity else '',
                         'accepted_at': identity.accepted_at if identity else None},
            'threads': threads,
            'opinions': {'articles': rows('article_opinions', 'article_id', 'polarity', 'body', 'created_at'),
                         'threads': rows('thread_opinions', 'thread_id', 'polarity', 'body', 'created_at'),
                         'community': rows('community_thread_opinions', 'thread_id', 'polarity', 'body', 'created_at'),
                         'diagnoses': rows('spin_opinions', 'diagnosis_id', 'polarity', 'body', 'created_at'),
                         'interviews': rows('interview_opinions', 'interview_id', 'polarity', 'created_at')},
            'clinic_comments': rows('clinic_comments', 'diagnosis_id', 'interview_id', 'parent_id', 'body', 'created_at', 'hidden_at', 'hidden_reason'),
            'clinic_reports': rows('clinic_comment_reports', 'comment_id', 'reason', 'details', 'created_at'),
            'comments_blocked_until': identity.comments_blocked_until if identity else None,
            'favorites': {'articles': rows('article_favorites', 'article_id', 'created_at'),
                          'threads': rows('thread_favorites', 'thread_id', 'created_at')},
            'follows': [follow_data(row) for row in Follow.objects.filter(user=user)],
        }, json_dumps_params={'ensure_ascii': False})
        response['Content-Disposition'] = 'attachment; filename="spin-clinic-konto.json"'
        response['Cache-Control'] = 'no-store'
        return response


class DeleteInput(serializers.Serializer):
    password = serializers.CharField(max_length=256, trim_whitespace=False)
    confirm = serializers.ChoiceField(choices=['USUŃ'])


class AccountDeleteView(APIView):
    permission_classes = [AccountEnabled, IsAuthenticated]
    throttle_classes = [AccountIPThrottle]

    def post(self, request):
        data = DeleteInput(data=request.data)
        data.is_valid(raise_exception=True)
        if not request.user.check_password(data.validated_data['password']):
            return Response({'password': ['Hasło jest nieprawidłowe. Konto Google: najpierw ustaw hasło przez e-mail.']}, status=400)
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            from news.notification_models import Notification, NotificationEvent
            thread_ids = list(user.personal_context_threads.values_list('pk', flat=True))
            Notification.objects.filter(url__in=[f'/nitki/{pk}' for pk in thread_ids]).delete()
            NotificationEvent.objects.filter(kind='thread', target_id__in=thread_ids).delete()
            user.delete()
        logout(request)
        return Response({'detail': 'Konto, jego dane oraz prywatne i publiczne nitki zostały usunięte.'})
