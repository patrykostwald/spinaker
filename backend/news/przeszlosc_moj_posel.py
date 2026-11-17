"""„Mój poseł” (przeszłość.today, 6.11.2026): wybierz okręg wyborczy, zobacz posłów z tego okręgu.

Dane: aktywna lista posłów z oficjalnego API Sejmu (ParliamentaryRosterEntry, pole district), powiązana z rejestrem osób
publicznych. Bez sieci, bez AI. Okręg to nazwa z API Sejmu (np. „Kraków”, „Warszawa”); posłowie z klubem i odnośnikiem do profilu.
Brak posła w wyniku znaczy „brak w naszych danych”: rejestr osób może nie mieć jeszcze każdego posła.
"""
from collections import defaultdict

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from news.przeszlosc_osoba import display_name, slug


def _entries():
    from news.political_models import ParliamentaryRosterEntry
    return ParliamentaryRosterEntry.objects.filter(source='sejm', active=True).exclude(district='')


def districts():
    """Lista okręgów w kolejności alfabetycznej z liczbą posłów."""
    counts = defaultdict(int)
    for district in _entries().values_list('district', flat=True):
        counts[district.strip()] += 1
    return [{'name': name, 'mps': counts[name]} for name in sorted(counts, key=lambda n: n.casefold())]


def district_members(name):
    """Posłowie jednego okręgu; zwraca None, gdy takiego okręgu nie ma."""
    from news.political_models import PublicFigure
    entries = list(_entries().filter(district__iexact=name.strip()).order_by('full_name'))
    if not entries:
        return None
    figures = {f.parliamentary_roster_entry_id: f for f in
               PublicFigure.objects.filter(parliamentary_roster_entry__in=entries, archived=False, merged_into__isnull=True)}
    from news import voting_anomalies
    snap = voting_anomalies.snapshot(None, '90d')
    stats = (snap.data.get('members') if snap else None) or {}
    members = []
    for e in entries:
        f = figures.get(e.pk)
        row = stats.get(f'{e.external_id}:{e.club}') or {}
        members.append({'name': display_name(e.full_name), 'club': e.club, 'slug': slug(f) if f else None, 'id': f.pk if f else None,
                        'sejm_id': int(e.external_id) if str(e.external_id).isdigit() else None, 'sejm_url': e.profile_url,
                        # odstępstwa od klubu w ostatnich 90 dniach (nocne przeliczenie): udział głosów innych niż większość klubu
                        'deviation_share': row.get('share'), 'deviation_votes': row.get('counted')})
    return {'district': entries[0].district, 'total': len(members), 'members': members}


@api_view(['GET'])
@permission_classes([AllowAny])
def moj_posel_view(request):
    """GET /api/przeszlosc/moj-posel/ (lista okręgów) albo ?okreg=Kraków (posłowie okręgu)."""
    from news.przeszlosc import enabled
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    name = (request.query_params.get('okreg') or '').strip()[:80]
    if not name:
        return Response({'districts': districts(), 'source': 'Oficjalne API Sejmu (lista aktywnych posłów).'})
    data = district_members(name)
    if data is None:
        return Response({'detail': 'Nie ma takiego okręgu w naszych danych.'}, status=404)
    return Response(data)
