"""Stan danych przeszłość.today (Śledczy G4, sprint 23.10): „czy brak wyniku to brak w świecie, czy brak w bazie?”

Dla każdego źródła: czy zbieranie jest włączone, ile mamy rekordów, kiedy ostatnio pobraliśmy dane, ostatni błąd i znane
braki. Zbieracz bez udanego pobrania dłużej niż 48 h (przy włączonym harmonogramie) jest oznaczony jako „zaległy”.
Na dole pokrycie KRS (krs_pokrycie.raport). Bez sieci; liczby z naszej bazy.
"""
import os
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Max
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

STALE_HOURS = 48
# Źródła spoza zbieraczy collect_public_*: (klucz w PublicRecord.source, nazwa, flaga harmonogramu, domyślnie, znane braki)
EXTRA = [
    ('bzp', 'Biuletyn Zamówień Publicznych (ezamowienia.gov.pl)', 'BZP_API_ENABLED', False,
     'Ogłoszenia zamawiających po NIP; BZP nie podaje wykonawcy ani kwoty w metadanych.'),
    ('niw', 'Lista dotacji NIW-CRSO', 'PRZESZLOSC_NIW_AUTO', True, 'Tylko umowy z numerem KRS; plik raz w tygodniu.'),
    ('mf_opp', 'Wykaz OPP - 1,5% podatku (Ministerstwo Finansów)', 'PRZESZLOSC_OPP_AUTO', True,
     'Kwoty wskazań podatników, poza dotacjami i sumami.'),
]
GAPS = {
    'ted': 'Ogłoszenia od 10.2025 (okno zbieracza); kwota to wartość ogłoszenia, nie umowy.',
    'fts': 'Beneficjenci budżetu UE zarządzanego przez KE; dopasowanie po VAT.',
    'kohesio': 'Dopasowanie tylko po nazwie - pokazywane osobno, poza sumami.',
    'meta_ads': 'Archiwum do 5.10.2025 (TTPA).',
    'krs_changes': 'Tylko podmioty, które już mamy w bazie.',
}


def _flag(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def sources():
    from news.public_records_models import PublicCollectionState, PublicRecord
    from scraper.public_records import SOURCES
    now = timezone.now()
    stats = {row['source']: row for row in PublicRecord.objects.values('source').annotate(n=Count('pk'), last=Max('fetched_at'))}
    states = {s.source: s for s in PublicCollectionState.objects.all()}
    rows = []
    entries = [(key, spec.title, spec.flag(key), False, GAPS.get(key, '')) for key, spec in SOURCES.items()] + EXTRA
    for key, title, flag, default, gaps in entries:
        stat = stats.get(key) or {}
        state = states.get(key)
        last = (state.last_success_at if state and state.last_success_at else None) or stat.get('last')
        on = _flag(flag, default)
        if not on:
            status = 'off'
        elif last is None:
            status = 'empty'
        elif now - last > timedelta(hours=STALE_HOURS):
            status = 'stale'
        else:
            status = 'ok'
        rows.append({'key': key, 'title': title, 'enabled': on, 'status': status, 'records': stat.get('n', 0),
                     'last_fetch': last.isoformat(timespec='minutes') if last else None,
                     'last_error': (state.last_error if state else '') or '', 'gaps': gaps})
    order = {'stale': 0, 'empty': 1, 'ok': 2, 'off': 3}
    rows.sort(key=lambda r: (order[r['status']], -r['records']))
    return rows


def krs_summary():
    from news import krs_pokrycie
    data = krs_pokrycie.raport()
    o, p = data['osoby'], data['podmioty']
    return {'people_total': o['wszystkie'], 'people_checked': o['sprawdzone_w_krs'], 'people_with_entity': o['z_potwierdzonym_podmiotem'],
            'relations_confirmed': o['relacje_potwierdzone'], 'relations_pending': o['relacje_do_przegladu'],
            'entities_total': p['wszystkie'], 'entities_with_nip': p['z_nip'], 'entities_stale': p['odpis_stary'],
            'queue': data['kolejka']['wedlug_stanu'], 'agent_enabled': o['agent_wlaczony'], 'rules': data['zasady']}


def payload():
    rows = sources()
    return {'generated_at': timezone.now().isoformat(timespec='minutes'), 'stale_hours': STALE_HOURS, 'sources': rows,
            'counts': {s: sum(1 for r in rows if r['status'] == s) for s in ('ok', 'stale', 'empty', 'off')},
            'krs': krs_summary(),
            'note': 'Brak wyniku w przeszłość.today znaczy „brak w naszych danych”, nie „brak w świecie”. '
                    'Źródło wyłączone albo zaległe może nie mieć najnowszych rekordów.'}


@api_view(['GET'])
@permission_classes([AllowAny])
def view(request):
    """GET /api/przeszlosc/stan-danych/ - stan każdego źródła i pokrycie KRS (cache 10 min)."""
    from news.przeszlosc import enabled
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    data = cache.get('przeszlosc:stan-danych')
    if data is None:
        data = payload()
        cache.set('przeszlosc:stan-danych', data, 600)
    return Response(data)
