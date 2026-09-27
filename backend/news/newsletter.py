"""Newsletter „powiadom mnie o starcie”: zapis z podwójnym potwierdzeniem (RODO), wypisanie jednym kliknięciem, statystyki.

Poczta idzie przez tę samą skrzynkę SMTP co alerty Kliniki (SOURCE_MAIL_SMTP_*). Odpowiedź na zapis jest zawsze
taka sama — nie zdradzamy, czy adres już jest na liście.
"""
import logging
import os
import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from news.newsletter_models import NewsletterSubscriber

logger = logging.getLogger(__name__)

CONSENT_VERSION = '2026-09-27'
CONSENT_TEXT = ('Zgadzam się na otrzymywanie od spin.clinic (iapply sp. z o.o.) e-maili o starcie serwisu i jego nowościach. '
                'Mogę się wypisać w każdej chwili jednym kliknięciem.')
RESEND_AFTER = timedelta(minutes=10)
CHECK_EMAIL = {'status': 'check_email', 'detail': 'Sprawdź skrzynkę — wysłaliśmy link potwierdzający zapis.'}


class NewsletterThrottle(AnonRateThrottle):
    scope = 'newsletter'
    rate = '5/hour'


def _site() -> str:
    return 'https://' + os.environ.get('SPIN_DOMAIN', 'spin.clinic')


def smtp_ready() -> bool:
    required = ('SOURCE_MAIL_SMTP_HOST', 'SOURCE_MAIL_SMTP_USERNAME', 'SOURCE_MAIL_SMTP_PASSWORD', 'SOURCE_MAIL_SMTP_FROM')
    return bool(settings.SOURCE_MAIL_SMTP_ENABLED and all(getattr(settings, item, '') for item in required))


def send_confirmation(subscriber_id: int) -> str:
    subscriber = NewsletterSubscriber.objects.filter(pk=subscriber_id, status='pending').first()
    if not subscriber:
        return 'skipped'
    if not smtp_ready():
        logger.warning('newsletter: SMTP not configured, confirmation not sent')
        return 'no_smtp'
    link = f'{_site()}/newsletter/potwierdz?t={subscriber.token}'
    unsubscribe = f'{_site()}/newsletter/wypisz?t={subscriber.token}'
    email = EmailMessage()
    email['From'] = settings.SOURCE_MAIL_SMTP_FROM
    email['To'] = subscriber.email
    email['Subject'] = 'Potwierdź zapis — spin.clinic'
    email.set_content(
        'Dzień dobry,\n\n'
        'ktoś (mamy nadzieję, że Ty) zapisał ten adres na powiadomienie o starcie spin.clinic.\n'
        f'Żeby potwierdzić, kliknij:\n{link}\n\n'
        'Jeśli to nie Ty — zignoruj tę wiadomość. Bez potwierdzenia nie wyślemy nic więcej.\n'
        f'Wypisanie w każdej chwili: {unsubscribe}\n\n'
        'spin.clinic — Klinika spinu i wiadomości ze źródłami\n'
        'iapply sp. z o.o., pl. Wolności 16, 61-739 Poznań · admin@spin.clinic')
    try:
        with smtplib.SMTP_SSL(settings.SOURCE_MAIL_SMTP_HOST, settings.SOURCE_MAIL_SMTP_PORT, timeout=20) as client:
            client.login(settings.SOURCE_MAIL_SMTP_USERNAME, settings.SOURCE_MAIL_SMTP_PASSWORD)
            client.send_message(email)
    except (OSError, smtplib.SMTPException) as error:
        logger.warning('newsletter confirmation failed: %s', type(error).__name__)
        return 'failed'
    NewsletterSubscriber.objects.filter(pk=subscriber.pk).update(confirmation_sent_at=timezone.now())
    return 'sent'


def _queue_confirmation(subscriber_id: int) -> None:
    from news.tasks import newsletter_confirmation_task
    transaction.on_commit(lambda: newsletter_confirmation_task.delay(subscriber_id))


@extend_schema(summary='Zapis na powiadomienie o starcie (podwójne potwierdzenie)', tags=['newsletter'], responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([NewsletterThrottle])
def subscribe(request):
    if request.data.get('website'):  # pole-pułapka dla botów, niewidoczne dla ludzi
        return Response(CHECK_EMAIL)
    email = str(request.data.get('email', '')).strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return Response({'detail': 'Podaj poprawny adres e-mail.'}, status=400)
    if request.data.get('consent') is not True:
        return Response({'detail': 'Zaznacz zgodę na otrzymywanie wiadomości.'}, status=400)
    source = str(request.data.get('source', ''))[:64]
    now = timezone.now()
    with transaction.atomic():
        subscriber = NewsletterSubscriber.objects.select_for_update().filter(email=email).first()
        if subscriber is None:
            subscriber = NewsletterSubscriber.objects.create(email=email, token=secrets.token_urlsafe(32),
                                                             consent_version=CONSENT_VERSION, source=source)
        elif subscriber.status == 'confirmed':
            return Response(CHECK_EMAIL)  # już na liście — nic nie wysyłamy, odpowiedź taka sama
        elif subscriber.status == 'pending' and subscriber.confirmation_sent_at and now - subscriber.confirmation_sent_at < RESEND_AFTER:
            return Response(CHECK_EMAIL)
        else:
            subscriber.status, subscriber.token = 'pending', secrets.token_urlsafe(32)
            subscriber.consent_version, subscriber.source, subscriber.unsubscribed_at = CONSENT_VERSION, source, None
            subscriber.save(update_fields=['status', 'token', 'consent_version', 'source', 'unsubscribed_at'])
        _queue_confirmation(subscriber.pk)
    return Response(CHECK_EMAIL)


def _by_token(request):
    token = str(request.data.get('token', '')).strip()
    return NewsletterSubscriber.objects.filter(token=token).first() if len(token) >= 20 else None


@extend_schema(summary='Potwierdzenie zapisu na newsletter', tags=['newsletter'], responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def confirm(request):
    subscriber = _by_token(request)
    if subscriber is None or subscriber.status == 'unsubscribed':
        return Response({'detail': 'Link wygasł albo jest niepoprawny. Zapisz się ponownie.'}, status=404)
    if subscriber.status == 'pending':
        subscriber.status, subscriber.confirmed_at = 'confirmed', timezone.now()
        subscriber.save(update_fields=['status', 'confirmed_at'])
    return Response({'status': 'confirmed', 'unsubscribe_token': subscriber.token})


@extend_schema(summary='Wypisanie z newslettera jednym kliknięciem', tags=['newsletter'], responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def unsubscribe(request):
    subscriber = _by_token(request)
    if subscriber is None:
        return Response({'detail': 'Ten adres jest już wypisany albo link jest niepoprawny.'}, status=404)
    if subscriber.status != 'unsubscribed':
        subscriber.status, subscriber.unsubscribed_at = 'unsubscribed', timezone.now()
        subscriber.save(update_fields=['status', 'unsubscribed_at'])
    return Response({'status': 'unsubscribed'})


def stats(days: int = 14) -> dict:
    counts = dict(NewsletterSubscriber.objects.values_list('status').annotate(n=Count('id')))
    since = timezone.now() - timedelta(days=days)
    daily = (NewsletterSubscriber.objects.filter(confirmed_at__gte=since).annotate(day=TruncDate('confirmed_at'))
             .values('day').annotate(n=Count('id')).order_by('day'))
    return {'confirmed': counts.get('confirmed', 0), 'pending': counts.get('pending', 0),
            'unsubscribed': counts.get('unsubscribed', 0),
            'confirmed_last_7_days': NewsletterSubscriber.objects.filter(confirmed_at__gte=timezone.now() - timedelta(days=7)).count(),
            'daily': [{'day': row['day'], 'confirmed': row['n']} for row in daily], 'smtp_ready': smtp_ready()}


@extend_schema(summary='Newsletter: liczba zapisów (dla zespołu)', tags=['newsletter'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def staff_stats(request):
    return Response(stats())
