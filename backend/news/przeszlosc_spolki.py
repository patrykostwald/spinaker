"""Wyszukiwarka podmiotów przeszłość.today (P1-1): nazwa, KRS, NIP, REGON + dociąganie KRS na żądanie z api-krs.

Tylko oficjalne publiczne API KRS (krs.fetch), dane podmiotu bez osób (nie zapisujemy nic o osobach). Grzeczność wobec API:
cache wyników (także „nie ma”), limit pobrań na minutę globalnie i na adres IP, krótka pamięć błędów sieci.
Nazwy szukamy tylko w naszych danych (API KRS nie ma wyszukiwania po nazwie); NIP i REGON tak samo - to zawsze mówimy wprost.
"""
import re

from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from news import krs as krs_client

FETCH_PER_MINUTE = 20      # globalnie
FETCH_PER_IP_MINUTE = 5
MISSING_TTL = 6 * 3600     # „nie ma w rejestrze” pamiętamy kilka godzin
ERROR_TTL = 120            # błąd sieci/API - krótko, żeby nie młotkować
LIMIT = 15

SCOPE = ('Przeszukujemy podmioty, które mamy w bazie (spółki, fundacje i stowarzyszenia z KRS powiązane z osobami publicznymi i zamówieniami). '
         'Numer KRS możemy dociągnąć z rejestru na żądanie; nazwy, NIP i REGON szukamy tylko w naszych danych.')


def classify(query):
    """('krs'|'nip'|'regon'|'digits'|'name'|'', wartość) - 10 cyfr zaczynających się od 00 to KRS, inne 10 cyfr to NIP."""
    q = str(query or '').strip()
    d = re.sub(r'\D', '', q)
    if d and re.fullmatch(r'(?i)\s*(krs|nip|regon)?[\s:.\-0-9]*', q):
        label = re.match(r'(?i)\s*(krs|nip|regon)', q)
        if label:
            return label.group(1).lower(), d
        if len(d) == 10 and d.startswith('00'):
            return 'krs', d
        if len(d) == 10:
            return 'nip', d
        if len(d) in (9, 14):
            return 'regon', d
        if len(d) <= 7:
            return 'krs', d.zfill(10)   # krótki numer: najpewniej KRS bez zer
        return 'digits', d
    return ('name', q) if len(q) >= 3 else ('', q)


def looks_like_krs(value):
    d = re.sub(r'\D', '', str(value or ''))
    return len(d) == 10 and d.startswith('00')


def card(org):
    return {'id': org.pk, 'name': org.name, 'krs_number': org.krs_number, 'nip': org.nip, 'regon': org.regon, 'kind': org.kind,
            'legal_form': org.legal_form, 'url': f'/przeszlosc/spolka/{org.krs_number}'}


def _allow(ip):
    """Limit grzeczności dla pobrań z api-krs: licznik na minutę, globalnie i na adres IP."""
    minute = timezone.now().strftime('%Y%m%d%H%M')
    for key, cap in ((f'przeszlosc:krs-limit:{minute}', FETCH_PER_MINUTE), (f'przeszlosc:krs-limit:{minute}:{ip}', FETCH_PER_IP_MINUTE)):
        cache.add(key, 0, 120)
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, 120)
            count = 1
        if count > cap:
            return False
    return True


def fetch_on_demand(number, ip='-'):
    """(RegisteredOrganisation | None, status): ok | missing | busy | error. Nie rzuca wyjątków."""
    from news.political_models import RegisteredOrganisation
    number = krs_client.normalize_krs(number)
    if not number:
        return None, 'missing'
    known = RegisteredOrganisation.objects.filter(krs_number=number).first()
    if known:
        return (None, 'missing') if known.archived else (known, 'ok')
    flag = cache.get(f'przeszlosc:krs-neg:{number}')
    if flag:
        return None, flag
    if not _allow(ip):
        return None, 'busy'
    try:
        extract = krs_client.fetch(number, full=False)
    except Exception:  # noqa: BLE001 - sieć i parser nie mogą wywrócić widoku
        cache.set(f'przeszlosc:krs-neg:{number}', 'error', ERROR_TTL)
        return None, 'error'
    if extract is None or not extract.name:
        # fetch() zwraca None i dla 404, i dla błędu sieci: pamiętamy krótko, żeby nie młotkować rejestru
        cache.set(f'przeszlosc:krs-neg:{number}', 'missing', ERROR_TTL)
        return None, 'missing'
    org, _ = RegisteredOrganisation.objects.update_or_create(krs_number=extract.krs, defaults={
        'name': extract.name.strip()[:512], 'kind': extract.kind, 'legal_form': extract.legal_form.lower()[:128], 'register': extract.register,
        'official_register_url': extract.public_url, 'sector': extract.sector, 'source_checked_at': timezone.now(),
        **{k: v for k, v in (('nip', extract.nip), ('regon', extract.regon)) if v}})
    return org, 'ok'


def _ip(request):
    return (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '-'))[:45]


def coverage():
    from news.political_models import RegisteredOrganisation
    return {'organisations': RegisteredOrganisation.objects.filter(archived=False).count(), 'scope': SCOPE}


def search(query, ip='-'):
    from news.political_models import RegisteredOrganisation
    base = RegisteredOrganisation.objects.filter(archived=False)
    kind, value = classify(query)
    out = {'query': str(query or '').strip(), 'mode': kind, 'results': [], 'fetched': False, 'status': 'ok', 'coverage': coverage()}
    if not kind:
        out['status'] = 'short'
        out['message'] = 'Wpisz co najmniej 3 znaki nazwy albo numer KRS, NIP lub REGON.'
        return out
    if kind == 'krs':
        number = krs_client.normalize_krs(value)
        hit = base.filter(krs_number=number).first()
        if not hit:
            hit, status = fetch_on_demand(number, ip)
            out['fetched'] = bool(hit)
            out['status'] = status
        hits = [hit] if hit else []
    elif kind == 'nip':
        hits = list(base.filter(nip=value)[:LIMIT])
    elif kind == 'regon':
        hits = list(base.filter(regon__in={value, value[:9]})[:LIMIT])
    elif kind == 'digits':
        hits = list(base.filter(Q(nip=value) | Q(regon=value) | Q(krs_number=value.zfill(10)))[:LIMIT])
    else:
        hits = list(base.filter(name__icontains=value).order_by('name')[:LIMIT])
    out['results'] = [card(o) for o in hits]
    if hits:
        out['status'] = 'ok'
    else:
        label = {'krs': 'numeru KRS', 'nip': 'NIP', 'regon': 'REGON', 'digits': 'numeru', 'name': 'nazwy'}[kind]
        if out['status'] == 'busy':
            out['message'] = 'Za dużo pobrań z rejestru KRS naraz. Spróbuj za minutę.'
        elif out['status'] == 'error':
            out['message'] = 'Rejestr KRS chwilowo nie odpowiada. Spróbuj za kilka minut.'
        else:
            out['status'] = 'missing'
            if kind == 'krs':
                extra = ' Nie znaleźliśmy go też w rejestrze KRS (albo rejestr chwilowo nie odpowiedział).'
            else:
                extra = ' Szukamy tylko wśród podmiotów, które już mamy; wpisz numer KRS, a pobierzemy go z rejestru.'
            out['message'] = f'Brak w naszych danych: nie znaleźliśmy podmiotu po {label} „{out["query"]}”.{extra}'
    return out


@api_view(['GET'])
@permission_classes([AllowAny])
def search_view(request):
    """GET /api/przeszlosc/spolki/?q=PKO | 0000026438 | NIP | REGON - wyszukiwarka podmiotów."""
    from news.przeszlosc import enabled
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    return Response(search(request.GET.get('q', '')[:80], _ip(request)))
