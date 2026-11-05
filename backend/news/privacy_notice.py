"""Klauzula informacyjna art. 14 RODO w profilu osoby przeszłość.today i przyjmowanie sprzeciwu (art. 21).

SZKIC DO PRAWNIKA (decyzja właściciela 13.10): treść, podstawa prawna i okresy przechowywania wymagają potwierdzenia
(pytania 1, 2 i 11 z recenzji Fable). Flaga PRZESZLOSC_PRIVACY_NOTICE_ENABLED (domyślnie wyłączona) - przy wyłączonej
profil nie ma pola `privacy_notice`, a endpoint sprzeciwu zwraca 404.

Sprzeciw: kolejka personelu (komenda `sprzeciwy`), bez automatycznego usuwania danych; potwierdzenie adresu e-mail linkiem
(48 h), decyzja z uzasadnieniem wysyłana na potwierdzony adres.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

VERSION = 'art14-szkic-1'
DATE = '2026-10-13'
STATUS = 'szkic do prawnika'
SECTIONS = [
    ('Kto przetwarza dane', 'Administratorem danych w serwisie przeszłość.today jest iapply sp. z o.o. z siedzibą w Poznaniu. '
                            'Kontakt w sprawie danych: kontakt@iapply.pl.'),
    ('Po co', 'Pokazujemy publiczną działalność osób pełniących funkcje publiczne: wypowiedzi, głosowania, dokumenty '
              'i powiązania z rejestrów jawnych, z datą i źródłem każdej informacji. Nie oceniamy osób.'),
    ('Na jakiej podstawie', 'Prawnie uzasadniony interes i interes publiczny w jawności życia publicznego '
                            '(art. 6 ust. 1 lit. f i e RODO; ewentualnie art. 85 RODO i przepisy o działalności dziennikarskiej). '
                            'Podstawa do potwierdzenia przez prawnika.'),
    ('Skąd mamy dane', 'Wyłącznie ze źródeł publicznych: Sejm RP (API i strony), Dziennik Ustaw i Monitor Polski, KRS, '
                       'rejestry zamówień i dotacji, wykazy organizacji, publiczne konta osób w serwisie X potwierdzone przy '
                       'osobie. Przy każdej informacji podajemy źródło i datę pobrania.'),
    ('Jakie dane', 'Imię i nazwisko, pełnione funkcje, publiczne wypowiedzi i głosowania, funkcje w podmiotach z KRS, '
                   'dokumenty urzędowe z udziałem osoby. Nie przetwarzamy danych szczególnych kategorii.'),
    ('Jak długo', 'Dopóki informacja dotyczy pełnionej funkcji publicznej i jest dostępna w źródle publicznym; okres do '
                  'potwierdzenia przez prawnika.'),
    ('Twoje prawa', 'Masz prawo dostępu do danych, ich sprostowania, ograniczenia przetwarzania, sprzeciwu wobec '
                    'przetwarzania (art. 21 RODO) oraz skargi do Prezesa UODO. Sprzeciw rozpatruje człowiek, decyzję '
                    'z uzasadnieniem wysyłamy na potwierdzony adres e-mail.'),
    ('Jak złożyć sprzeciw', 'Formularzem przy profilu albo pod adresem kontakt@iapply.pl. Potwierdź adres e-mail linkiem, '
                            'który wyślemy (ważny 48 godzin).'),
]


def enabled() -> bool:
    from news.v3_flags import flag
    return flag('PRZESZLOSC_PRIVACY_NOTICE_ENABLED')


def notice(figure) -> dict:
    from news.przeszlosc_osoba import slug
    return {'version': VERSION, 'date': DATE, 'status': STATUS, 'title': 'Informacja o przetwarzaniu danych (art. 14 RODO)',
            'sections': [{'heading': h, 'text': t} for h, t in SECTIONS],
            'objection_url': f'/api/przeszlosc/osoba/{slug(figure)}/sprzeciw/', 'contact': 'kontakt@iapply.pl'}


def extend_profile(data: dict, figure) -> dict:
    if enabled():
        data['privacy_notice'] = notice(figure)
    return data


def submit(figure, reason, contact, relation, *, ip=None, ident=''):
    """Sprzeciw do kolejki. Recenzja Codex 3: przyjmowany tak samo dla istniejącego i nieistniejącego profilu (bez
    enumeracji); token w bazie jako skrót, jednorazowy, z terminem."""
    from news import v3_tokens
    from news.clinic_models import DataObjection
    from news.position_pairs import _mail, _site, ip_hash
    token, token_hash = v3_tokens.new()
    hours = int(getattr(settings, 'POSITION_PAIR_CONFIRM_HOURS', 48))
    row = DataObjection.objects.create(figure=figure, ident=str(ident)[:120], reason=reason[:2000], contact=contact.strip()[:200],
                                       relation=relation, confirm_token=token_hash, ip_hash=ip_hash(ip), notice_version=VERSION,
                                       token_expires_at=timezone.now() + timedelta(hours=hours))
    label = figure.canonical_name if figure else f'profil {str(ident)[:60]}'
    _mail(row.contact, 'Potwierdź sprzeciw dotyczący profilu w przeszłość.today',
          f'Otrzymaliśmy sprzeciw dotyczący: {label}. Jeśli to Ty go wysłałeś(-aś), potwierdź adres '
          f'w ciągu {hours} godzin: {_site()}/api/przeszlosc/sprzeciw/potwierdz/{token}/\n\n'
          'Sprzeciw rozpatrzy człowiek; decyzję z uzasadnieniem wyślemy na ten adres. Jeśli to nie Ty, zignoruj tę wiadomość.\n'
          'Kontakt: kontakt@iapply.pl')
    return row


def confirm(token, now=None):
    from news import v3_tokens
    from news.clinic_models import DataObjection
    now = now or timezone.now()
    row = v3_tokens.find(DataObjection.objects.exclude(confirm_token=''), 'confirm_token', token)
    if row is None:
        raise LookupError('token')
    if row.token_used_at or row.email_confirmed_at:
        raise TimeoutError('used')  # jednorazowy
    expires = row.token_expires_at or row.created_at + timedelta(hours=int(getattr(settings, 'POSITION_PAIR_CONFIRM_HOURS', 48)))
    if now > expires:
        raise TimeoutError('expired')
    row.email_confirmed_at, row.token_used_at, row.status = now, now, 'potwierdzony'
    row.save(update_fields=['email_confirmed_at', 'token_used_at', 'status'])
    return row


DECISIONS = {'uwzgledniony': 'Sprzeciw został uwzględniony. Zakres zmian opisujemy w uzasadnieniu.',
             'odrzucony': 'Sprzeciw nie został uwzględniony.'}


def decide(row, user, decision, note):
    """Decyzja człowieka z uzasadnieniem; bez automatycznego usuwania danych (zmiany w profilu wykonuje personel ręcznie)."""
    from news.position_pairs import _mail
    if decision not in DECISIONS:
        raise ValueError('decision')
    if not note.strip():
        raise ValueError('note')
    with transaction.atomic():
        row.status, row.decision_note, row.decided_by, row.decided_at = decision, note[:600], user, timezone.now()
        row.save(update_fields=['status', 'decision_note', 'decided_by', 'decided_at'])
    if row.email_confirmed_at and row.contact and _mail(
            row.contact, 'Decyzja w sprawie sprzeciwu (przeszłość.today)',
            f'{DECISIONS[decision]}\nUzasadnienie: {note.strip()}\n\nMasz prawo wnieść skargę do Prezesa UODO.\nKontakt: kontakt@iapply.pl'):
        row.decision_sent_at = timezone.now()
        row.save(update_fields=['decision_sent_at'])
    return row


# --- API ---------------------------------------------------------------------------------------------------------------

from rest_framework import serializers  # noqa: E402
from rest_framework.decorators import api_view, permission_classes, throttle_classes  # noqa: E402
from rest_framework.permissions import AllowAny  # noqa: E402
from rest_framework.response import Response  # noqa: E402

from news.position_pairs import ReportThrottle  # noqa: E402


class ObjectionInput(serializers.Serializer):
    reason = serializers.CharField(min_length=20, max_length=2000)
    contact = serializers.EmailField(max_length=200)
    relation = serializers.ChoiceField(choices=['osoba', 'przedstawiciel', 'inna'])


def _no_store(response):
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ReportThrottle])
def objection_view(request, ident):
    """POST /api/przeszlosc/osoba/<ident>/sprzeciw/ - sprzeciw (art. 21 RODO) do kolejki personelu."""
    from news.przeszlosc import enabled as przeszlosc_enabled
    if not enabled() or not przeszlosc_enabled():
        return _no_store(Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404))
    from news.przeszlosc_osoba import resolve
    serializer = ObjectionInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    # Bez enumeracji profili: ta sama odpowiedź 202 dla istniejącej i nieistniejącej osoby; personel widzi identyfikator.
    submit(resolve(ident), data['reason'], data['contact'], data['relation'], ip=ReportThrottle().get_ident(request), ident=ident)
    return _no_store(Response({'status': 'received', 'confirm_email_sent': True,
                               'detail': 'Wysłaliśmy link potwierdzający na podany adres (ważny 48 godzin).'}, status=202))


@api_view(['GET'])
@permission_classes([AllowAny])
def confirm_view(request, token):
    """GET /api/przeszlosc/sprzeciw/potwierdz/<token>/"""
    if not enabled():
        return _no_store(Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404))
    try:
        confirm(token)
    except LookupError:
        return _no_store(Response({'detail': 'Nieznany link potwierdzający.'}, status=404))
    except TimeoutError as error:
        detail = 'Ten link został już użyty.' if str(error) == 'used' else 'Link wygasł. Wyślij sprzeciw ponownie.'
        return _no_store(Response({'detail': detail}, status=410))
    return _no_store(Response({'status': 'confirmed'}))
