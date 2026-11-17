"""Zapytania „Raporty dla instytucji” i zgłoszenia pilotów przeszłość.today (plan finansowy 6.10, ruchy 6 i 9).

Kanał przychodzący zamiast zimnych e-maili (PKE art. 398): ktoś sam pisze przez formularz. Zapis czeka na potwierdzenie
linkiem z e-maila (podwójne potwierdzenie), dopiero potem właściciel dostaje ważny mail, a zaznaczona zgoda na newsletter
staje się potwierdzonym zapisem. Odpowiedź na zapis jest zawsze taka sama. Nie pytamy o poglądy ani przynależność partyjną:
ta sama oferta i te same warunki dla wszystkich.

Pętla „Zapytania” (co godzinę, bez AI): ponawia nieudane maile potwierdzające i powiadomienia właściciela,
usuwa niepotwierdzone zgłoszenia po 30 dniach (minimalizacja danych).
"""
import logging
import os
import secrets
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from news.sales_models import SalesLead

logger = logging.getLogger(__name__)

CONSENT_VERSION = '2026-10-06'
NEWSLETTER_CONSENT = {
    'raporty': 'Zgadzam się na e-maile spin.clinic (iapply sp. z o.o.) z bezpłatną próbką raportu tygodniowego i informacjami '
               'o raportach. Mogę się wypisać jednym kliknięciem.',
    'pilot': 'Zgadzam się na e-maile przeszłość.today (iapply sp. z o.o.) o pilotażu i nowych funkcjach. '
             'Mogę się wypisać jednym kliknięciem.',
}
CHECK_EMAIL = {'status': 'check_email',
               'detail': 'Sprawdź skrzynkę - wysłaliśmy link potwierdzający. Bez potwierdzenia nie odezwiemy się.'}
LIMITS = {'name': 120, 'organisation': 160, 'message': 2000}
PENDING_TTL = timedelta(days=30)
RESEND_AFTER = timedelta(minutes=10)


class LeadThrottle(AnonRateThrottle):
    scope = 'sales_lead'
    rate = '5/hour'


class TokenThrottle(AnonRateThrottle):
    scope = 'sales_lead_token'
    rate = '30/hour'


def _site(kind):
    if kind == 'pilot':
        return 'https://' + os.environ.get('PRZESZLOSC_DOMAIN', 'przeszlosc.today')
    return 'https://' + os.environ.get('SPIN_DOMAIN', 'spin.clinic')


def confirm_url(lead):
    path = '/przeszlosc/pilot' if lead.kind == 'pilot' else '/dla-redakcji'
    return f'{_site(lead.kind)}{path}?potwierdz={lead.token}'


def owner_address():
    from news.raport_petli import recipient
    return os.environ.get('SALES_LEAD_EMAIL', '').strip() or recipient() or 'kontakt@spin.clinic'


def pilot_days():
    try:
        return max(1, int(os.environ.get('PRZESZLOSC_PILOT_DAYS', '60')))
    except ValueError:
        return 60


def send_confirmation(lead_id):
    from news.account_mail import send_account_mail
    lead = SalesLead.objects.filter(pk=lead_id, status='pending').first()
    if not lead:
        return 'skipped'
    if lead.kind == 'pilot':
        from news.przeszlosc_dostep import beta
        perk = ('w becie wszystkie funkcje są bezpłatne dla każdego, a pilot daje bezpośredni kanał do zespołu.' if beta()
                else f'piloci dostają bezpłatny dostęp do wszystkich funkcji na {pilot_days()} dni.')
        what = ('zgłoszenie do pilotażu przeszłość.today. Po potwierdzeniu odezwiemy się w ciągu 2 dni roboczych; ' + perk)
        sign = 'przeszłość.today - iapply sp. z o.o., Poznań'
    else:
        what = ('zapytanie o raporty spin.clinic dla instytucji. Po potwierdzeniu odpowiemy w 1 dzień roboczy '
                'i wyślemy bezpłatną próbkę raportu tygodniowego.')
        sign = 'spin.clinic - iapply sp. z o.o., Poznań · kontakt@spin.clinic'
    body = ('Dzień dobry,\n\n'
            f'ktoś (mamy nadzieję, że Ty) wysłał z tego adresu {what}\n\n'
            f'Potwierdź tutaj:\n{confirm_url(lead)}\n\n'
            'Jeśli to nie Ty, zignoruj tę wiadomość. Bez potwierdzenia nie odezwiemy się, a zgłoszenie usuniemy po 30 dniach.\n\n'
            f'{sign}')
    if not send_account_mail(lead.email, 'Potwierdź zgłoszenie' + (' - przeszłość.today' if lead.kind == 'pilot' else ' - spin.clinic'), body):
        return 'failed'
    SalesLead.objects.filter(pk=lead.pk).update(confirmation_sent_at=timezone.now())
    return 'sent'


def notify_owner(lead):
    """Ważny mail do właściciela (idzie także przy wyłączonych powiadomieniach zespołu)."""
    from news.social_publish import _mail
    body = (f"Nowe potwierdzone zgłoszenie: {lead.get_kind_display()}\n\n"
            f"Kto: {lead.name}\nOrganizacja: {lead.organisation or '-'} ({lead.get_org_type_display()})\n"
            f"E-mail: {lead.email}\nNewsletter: {'tak (potwierdzony)' if lead.newsletter else 'nie'}\n\n"
            f"Wiadomość:\n{lead.message or '-'}\n\n"
            f"Panel: /admin/news/saleslead/{lead.pk}/change/\n"
            + ('Oferta prywatna PDF: akcja „Oferta prywatna (PDF)” w panelu. Ta sama oferta dla każdego odbiorcy.\n'
               if lead.kind == 'raporty' else
               f'Pilot: akcja „Przyznaj pilota Pro ({pilot_days()} dni)” w panelu. Te same warunki dla każdej redakcji.\n'))
    if _mail(owner_address(), f'Zgłoszenie: {lead.get_kind_display()} - {lead.organisation or lead.name}', body, important=True):
        SalesLead.objects.filter(pk=lead.pk).update(owner_notified_at=timezone.now())
        return True
    return False


def _newsletter(lead):
    """Zaznaczona zgoda + kliknięty link = podwójne potwierdzenie zapisu na newsletter."""
    from news.newsletter_models import NewsletterSubscriber
    if not lead.newsletter:
        return
    now = timezone.now()
    subscriber = NewsletterSubscriber.objects.filter(email=lead.email).first()
    source = 'przeszlosc-pilot' if lead.kind == 'pilot' else 'raporty-instytucje'
    if subscriber is None:
        NewsletterSubscriber.objects.create(email=lead.email, token=secrets.token_urlsafe(32), status='confirmed',
                                            consent_version=f'{lead.kind[0]}-{CONSENT_VERSION}', source=source,
                                            confirmed_at=now)
    elif subscriber.status != 'confirmed':
        subscriber.status, subscriber.confirmed_at, subscriber.unsubscribed_at = 'confirmed', now, None
        subscriber.consent_version, subscriber.source = f'{lead.kind[0]}-{CONSENT_VERSION}', source
        subscriber.save(update_fields=['status', 'confirmed_at', 'unsubscribed_at', 'consent_version', 'source'])


def _queue(lead_id):
    from news.tasks import sales_lead_confirmation_task
    transaction.on_commit(lambda: sales_lead_confirmation_task.delay(lead_id))


def create(kind, data):
    """Wspólny zapis dla obu formularzy. Zwraca (status HTTP, odpowiedź)."""
    if data.get('website'):  # pole-pułapka dla botów
        return 200, CHECK_EMAIL
    email = str(data.get('email', '')).strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return 400, {'detail': 'Podaj poprawny adres e-mail.'}
    fields = {k: str(data.get(k, '')).strip()[:limit] for k, limit in LIMITS.items()}
    if not fields['name']:
        return 400, {'detail': 'Podaj imię i nazwisko.'}
    org_type = str(data.get('org_type', 'inne'))
    if org_type not in dict(SalesLead.ORG_TYPES):
        org_type = 'inne'
    if data.get('privacy') is not True:
        return 400, {'detail': 'Zaznacz zgodę na kontakt w sprawie zgłoszenia.'}
    now = timezone.now()
    with transaction.atomic():
        recent = SalesLead.objects.select_for_update().filter(kind=kind, email=email, status='pending').first()
        if recent and recent.confirmation_sent_at and now - recent.confirmation_sent_at < RESEND_AFTER:
            return 200, CHECK_EMAIL
        lead = recent or SalesLead(kind=kind, email=email)
        lead.name, lead.organisation, lead.message, lead.org_type = fields['name'], fields['organisation'], fields['message'], org_type
        lead.newsletter = data.get('newsletter') is True
        lead.token, lead.consent_version, lead.created_at = secrets.token_urlsafe(32), CONSENT_VERSION, now
        lead.save()
        _queue(lead.pk)
    return 200, CHECK_EMAIL


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LeadThrottle])
def report_inquiry(request):
    status, payload = create('raporty', request.data)
    return Response(payload, status=status)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LeadThrottle])
def pilot_signup(request):
    status, payload = create('pilot', request.data)
    return Response(payload, status=status)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([TokenThrottle])
def confirm(request):
    token = str(request.data.get('token', '')).strip()
    lead = SalesLead.objects.filter(token=token).first() if len(token) >= 20 else None
    if lead is None:
        return Response({'detail': 'Link wygasł albo jest niepoprawny. Wyślij formularz ponownie.'}, status=404)
    if lead.status == 'pending':
        with transaction.atomic():
            lead.status, lead.confirmed_at = 'confirmed', timezone.now()
            lead.save(update_fields=['status', 'confirmed_at'])
            _newsletter(lead)
        notify_owner(lead)
    return Response({'status': 'confirmed', 'kind': lead.kind})


@api_view(['GET'])
@permission_classes([AllowAny])
def sample(request):
    from news.raport_tygodniowy import public_sample
    return Response(public_sample())


def grant_pilot(lead, today=None):
    today = today or timezone.localdate()
    lead.pilot_until = today + timedelta(days=pilot_days())
    if lead.status in ('pending', 'confirmed'):
        lead.status = 'contacted'
    lead.save(update_fields=['pilot_until', 'status'])
    return lead.pilot_until


def is_pilot_pro(email, today=None):
    """Flaga konta pilota: bezpłatny Pro do pilot_until (wspólna dla przyszłych funkcji Pro przeszłość.today)."""
    today = today or timezone.localdate()
    return SalesLead.objects.filter(kind='pilot', email=str(email).strip().lower(), pilot_until__gte=today).exists()


def run(now=None):
    """Pętla „Zapytania”: naprawy same, bez właściciela."""
    now = now or timezone.now()
    resent = notified = 0
    for lead in SalesLead.objects.filter(status='pending', confirmation_sent_at__isnull=True,
                                         created_at__lt=now - timedelta(minutes=30), created_at__gte=now - PENDING_TTL)[:20]:
        resent += send_confirmation(lead.pk) == 'sent'
    for lead in SalesLead.objects.filter(status='confirmed', owner_notified_at__isnull=True)[:20]:
        notified += notify_owner(lead)
    expired, _ = SalesLead.objects.filter(status='pending', created_at__lt=now - PENDING_TTL).delete()
    waiting = SalesLead.objects.filter(status='confirmed').count()
    return {'status': 'ok', 'resent': resent, 'notified': notified, 'expired': expired, 'waiting': waiting,
            'produced': resent + notified}
