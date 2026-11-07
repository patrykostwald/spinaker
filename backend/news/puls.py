"""Puls serwera dla paska centrum dowodzenia (właściciel 8.10): same liczby, bez treści maili i danych osobowych.

GET /api/puls/ z nagłówkiem X-Puls-Token (wartość PULS_TOKEN z env; porównanie stałoczasowe). Zwraca:
poczta (nowe, czekają decyzji, ostatni odczyt, błędy skrzynek), kopia_b2 (ok, czas), x (ostatni wpis, dziś),
diagnozy (dziś, ostatnia), dyzurny (otwarte alarmy). Pasek czyta to po stronie serwera panelu, token nie trafia do przeglądarki."""
import hmac
import os
from datetime import timedelta

from django.db.models import Max
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

NAGLOWEK = 'HTTP_X_PULS_TOKEN'


def token_ok(request):
    oczekiwany = os.environ.get('PULS_TOKEN', '').strip()
    if not oczekiwany:
        return None
    podany = request.META.get(NAGLOWEK, '')
    return hmac.compare_digest(podany.encode(), oczekiwany.encode())


def dane(now=None):
    from news.clinic_models import SpinDiagnosis
    from news.kopia_zapasowa import snapshot
    from news.models import Article, DutyAlarm
    from news.poczta_models import MailboxState, MailMessage

    now = now or timezone.now()
    dzis = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    kopia = snapshot()
    runs = kopia.get('runs') or []
    ostatnia_kopia = max(runs) if runs else kopia.get('last_db_at') or kopia.get('last_media_at')
    blad_kopii_at = kopia.get('last_error_at')
    kopia_ok = None if not (ostatnia_kopia or blad_kopii_at) else not (blad_kopii_at and (not ostatnia_kopia or blad_kopii_at > ostatnia_kopia))
    alarmy = list(DutyAlarm.objects.filter(status='open').order_by('-severity', 'since').values_list('rule', flat=True)[:8])
    return {
        'czas': now.isoformat(),
        'poczta': {
            'nowe': MailMessage.objects.filter(status='new').count(),
            'czekaja_decyzji': MailMessage.objects.filter(status='escalated', reply_sent_at__isnull=True).count(),
            'ostatni_odczyt': _iso(MailboxState.objects.aggregate(m=Max('last_ok_at'))['m']),
            'bledy': MailboxState.objects.filter(consecutive_errors__gt=0).count(),
        },
        'kopia_b2': {'ok': kopia_ok, 'czas': ostatnia_kopia},
        'x': {
            'ostatni': _iso(Article.objects.filter(ingestion_method='x').aggregate(m=Max('scraped_at'))['m']),
            'dzis': Article.objects.filter(ingestion_method='x', scraped_at__gte=dzis).count(),
        },
        'diagnozy': {
            'dzis': SpinDiagnosis.objects.filter(diagnosed_at__gte=dzis).count(),
            'ostatnia': _iso(SpinDiagnosis.objects.aggregate(m=Max('diagnosed_at'))['m']),
        },
        'dyzurny': {'bledy': len(alarmy), 'nazwy': alarmy},
        'okres_h': 24,
    }


def _iso(value):
    return value.isoformat() if value else None


@api_view(['GET'])
@permission_classes([AllowAny])
def puls(request):
    ok = token_ok(request)
    if ok is None:
        return Response({'detail': 'PULS_TOKEN nie jest ustawiony na serwerze.'}, status=503)
    if not ok:
        return Response({'detail': 'Zły token.'}, status=403)
    return Response(dane())
