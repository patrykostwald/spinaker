"""Łączy konta X z osobami z rejestru — wyłącznie na podstawie jawnych linków na oficjalnych profilach.

Kroki (dla każdej osoby):
1. Senat: pobiera oficjalny profil senatora (senat.gov.pl), zapisuje jawne linki do X jako dowody
   i odczytuje klub parlamentarny. PE: korzysta z dowodów z oficjalnych danych Parlamentu Europejskiego.
   Sejm blokuje automatyczne pobieranie profili (HTTP 403) — nie obchodzimy tego. Dla posłów
   (--wikidata) korzystamy z Wikidanych (CC0, właściwość P2002 „nazwa użytkownika X”) dopasowanych
   do aktualnego składu Sejmu po jednoznacznym imieniu i nazwisku; źródło zapisujemy w notatce.
2. Obóz (rządzący / opozycja) wynika z klubu lub frakcji; osoby bez jednoznacznego klubu pomijamy.
3. Jedno sprawdzenie konta w API X (ok. 0,01 USD), utworzenie konta i potwierdzenie przez wskazanego
   członka zespołu (--confirmed-by). Z --enable konto od razu trafia do czytania postów.

Bez --apply komenda tylko pokazuje plan i niczego nie zapisuje ani nie wysyła do X.
"""
import re

import requests
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.political_candidates import CandidateResolutionError, resolve_candidate
from news.political_models import ParliamentaryRosterEntry, PoliticalAccountCandidate, PublicFigure, SocialHandleEvidence
from news.social_handle_discovery import ALLOWED_PROFILE_HOSTS, SocialDiscoveryError, discover_for_entry

# Nazwa klubu na profilu senatora → kod klubu (jak w API Sejmu).
SENATE_CLUBS = [
    ('Koalicja Obywatelska', 'KO'), ('Prawo i Sprawiedliwość', 'PiS'), ('Polskie Stronnictwo Ludowe', 'PSL-TD'),
    ('Trzecia Droga', 'PSL-TD'), ('Polska 2050', 'Polska2050'), ('Lewica', 'Lewica'), ('Konfederacja', 'Konfederacja'),
    ('Razem', 'Razem'),
]
# Kod klubu Sejmu/Senatu albo frakcji PE → obóz. Brak na liście = obóz nieustalony (pomijamy).
CLUB_CAMPS = {
    'KO': 'government', 'PSL-TD': 'government', 'Polska2050': 'government', 'Lewica': 'government',
    'PiS': 'opposition', 'Konfederacja': 'opposition', 'Konfederacja_KP': 'opposition', 'Razem': 'opposition',
    # Frakcje PE: polscy europosłowie EPL to KO i PSL, S&D — Lewica, Renew — Polska 2050;
    # EKR (PiS), PfE i ESN (Konfederacja) — opozycja.
    'PPE': 'government', 'S&D': 'government', 'Renew': 'government',
    'ECR': 'opposition', 'PfE': 'opposition', 'ESN': 'opposition',
}
LOOKUP_USD = 0.01
INSTITUTIONAL_HANDLES = {'polskisenat', 'kancelariasejmu', 'europarl_pl', 'ep_poland', 'europarl_en'}


def senate_club(entry):
    """Klub z oficjalnego profilu senatora (ten sam host co dowód), albo ''."""
    url = entry.profile_url or entry.source_url
    host = (re.match(r'https://([^/]+)/', url or '') or [None, ''])[1].lower()
    if host not in ALLOWED_PROFILE_HOSTS['senat']:
        return ''
    try:
        response = requests.get(url, timeout=(5, 20), allow_redirects=False, headers={'Accept': 'text/html'})
    except requests.RequestException:
        return ''
    if response.status_code != 200:
        return ''
    text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', response.text))
    for match in re.finditer(r'Klub Parlamentarny ([^.,;]{3,90})', text):
        for name, code in SENATE_CLUBS:
            if name in match.group(1):
                return code
    return ''


def _fold(value):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFKD', value or '') if not unicodedata.combining(c)).casefold().replace('ł', 'l')


def official_identity(handle, full_name):
    """Tylko oficjalne konta: nazwa lub handle w X musi zawierać nazwisko osoby; konta chronione, parodie
    i fanowskie pomijamy. Zwraca (ok, powód)."""
    import os
    token = os.environ.get('X_POLITICAL_BEARER_TOKEN', '').strip()
    if not token:
        return False, 'brak tokenu X'
    try:
        response = requests.get(f'https://api.x.com/2/users/by/username/{handle}', timeout=(5, 15), allow_redirects=False,
                                params={'user.fields': 'name,username,description,protected'},
                                headers={'Authorization': f'Bearer {token}'})
        data = response.json().get('data') if response.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return False, 'X nie odpowiedział'
    if not data:
        return False, 'konto nie istnieje w X'
    if data.get('protected'):
        return False, 'konto chronione'
    text = _fold(f"{data.get('name', '')} {data.get('username', '')}")
    bio = _fold(data.get('description', ''))
    if any(word in bio for word in ('parod', 'fan ', 'fanpage', 'nieoficjaln', 'parody', 'not affiliated')):
        return False, 'opis wskazuje parodię lub konto nieoficjalne'
    surname = [part for part in _fold(full_name).replace('-', ' ').split() if len(part) > 2]
    if not surname or not any(part in text for part in surname[-2:]):
        return False, f'nazwa w X („{data.get("name", "")}”) nie zawiera nazwiska'
    return True, ''


def evidence_entry(evidence, figures_type):
    if evidence.roster_entry_id:
        return evidence.roster_entry, None
    if evidence.subject_content_type_id == figures_type.id and evidence.subject_object_id:
        figure = PublicFigure.objects.filter(pk=evidence.subject_object_id).select_related('parliamentary_roster_entry').first()
        return (figure.parliamentary_roster_entry if figure else None), figure
    return None, None


class Command(BaseCommand):
    help = 'Łączy konta X z rejestrem wyłącznie na podstawie jawnych linków na oficjalnych profilach (Senat, PE).'

    def add_arguments(self, parser):
        parser.add_argument('--skip-discovery', action='store_true', help='Nie pobieraj profili Senatu, użyj istniejących dowodów.')
        parser.add_argument('--wikidata', action='store_true', help='Posłowie: konta X z Wikidanych dopasowane do składu Sejmu.')
        parser.add_argument('--limit', type=int, default=200)
        parser.add_argument('--confirmed-by', default='', help='Nazwa użytkownika członka zespołu, który potwierdza konta.')
        parser.add_argument('--enable', action='store_true', help='Włącz czytanie postów z nowych kont.')
        parser.add_argument('--apply', action='store_true', help='Zapisz i sprawdź konta w X (płatne). Domyślnie tylko plan.')

    def handle(self, *args, **options):
        apply = options['apply']
        staff = None
        if apply:
            staff = get_user_model().objects.filter(username=options['confirmed_by'], is_staff=True, is_active=True).first()
            if not staff:
                raise CommandError('Podaj --confirmed-by z nazwą aktywnego członka zespołu (is_staff).')

        if not options['skip_discovery']:
            self._senate_discovery(apply, options['limit'])
        if options['wikidata']:
            self._wikidata_mps(apply)

        figures_type = ContentType.objects.get_for_model(PublicFigure)
        evidence_rows = SocialHandleEvidence.objects.filter(platform='x', status='pending_review').select_related('roster_entry')
        planned = skipped = linked = errors = 0
        for evidence in evidence_rows[:options['limit']]:
            entry, figure = evidence_entry(evidence, figures_type)
            club = (entry.club if entry else '') or getattr(self, '_clubs', {}).get(entry.pk if entry else None, '')
            camp = CLUB_CAMPS.get(club)
            name = entry.full_name if entry else (figure.canonical_name if figure else evidence.handle)
            if not camp:
                skipped += 1
                self.stdout.write(f'POMIŃ   @{evidence.handle} ({name}): obóz nieustalony (klub „{club or "brak"}”)')
                continue
            planned += 1
            if not apply:
                self.stdout.write(f'POŁĄCZ  @{evidence.handle} → {name} · {club} · {camp}')
                continue
            ok, reason = official_identity(evidence.handle, name)
            if not ok:
                skipped += 1
                evidence.status, evidence.reviewed_by, evidence.reviewed_at = 'rejected', staff, timezone.now()
                evidence.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
                self.stdout.write(f'POMIŃ   @{evidence.handle} ({name}): {reason}')
                continue
            candidate, _ = PoliticalAccountCandidate.objects.get_or_create(handle=evidence.handle, defaults={
                'display_name': name[:150], 'classification': camp, 'proposed_camp': camp,
                'confirmation_url': evidence.evidence_url,
                'confirmation_note': f'Jawny link do konta X na oficjalnym profilu: {evidence.extracted_url}. Klub: {club}.',
            })
            evidence.candidate, evidence.status = candidate, 'candidate_created'
            evidence.reviewed_by, evidence.reviewed_at = staff, timezone.now()
            evidence.save(update_fields=['candidate', 'status', 'reviewed_by', 'reviewed_at'])
            try:
                account = resolve_candidate(candidate, staff)
            except CandidateResolutionError as error:
                errors += 1
                self.stdout.write(f'BŁĄD    @{evidence.handle}: {error}')
                continue
            if options['enable'] and not account.enabled:
                account.enabled = True
                account.save(update_fields=['enabled'])
            linked += 1
            self.stdout.write(f'OK      @{account.handle} → {name} · {camp}{" · czytamy" if account.enabled else ""}')
        planned += getattr(self, '_senate_plan', 0)
        mode = 'ZAPISANO' if apply else 'PLAN (bez --apply nic nie zapisano i nie pytano X)'
        self.stdout.write(self.style.SUCCESS(
            f'{mode}: do połączenia {planned}, połączono {linked}, błędy {errors}, pominięte bez obozu {skipped}. '
            f'Koszt sprawdzeń w X ok. {planned * LOOKUP_USD * 2:.2f} USD (weryfikacja nazwy + utworzenie konta).'))

    def _senate_discovery(self, apply, limit):
        """Jawne linki X z profili senatorów. Konta z nagłówka i stopki strony (np. @PolskiSenat) odrzucamy:
        link, który występuje na wielu profilach, nie wskazuje konta konkretnej osoby."""
        from collections import Counter
        found, failed = {}, 0
        for entry in ParliamentaryRosterEntry.objects.filter(source='senat', active=True).order_by('pk')[:limit]:
            try:
                found[entry] = discover_for_entry(entry, persist=False)
            except SocialDiscoveryError:
                failed += 1
        counts = Counter(handle.lower() for links in found.values() for handle, _ in links)
        shared = {handle for handle, count in counts.items() if count > 2} | INSTITUTIONAL_HANDLES
        personal = 0
        for entry, links in found.items():
            own = [(handle, url) for handle, url in links if handle.lower() not in shared]
            if not own:
                continue
            club = entry.club or senate_club(entry)
            camp = CLUB_CAMPS.get(club)
            for handle, url in own:
                personal += 1
                if not apply:
                    self.stdout.write(f'{"POŁĄCZ " if camp else "POMIŃ  "} @{handle} → {entry.full_name} · Senat · {club or "klub nieustalony"}'
                                      + (f' · {camp}' if camp else ''))
                    self._senate_plan = getattr(self, '_senate_plan', 0) + (1 if camp else 0)
                    continue
                if club and not entry.club:
                    entry.club = club
                    entry.save(update_fields=['club'])
                evidence, created = SocialHandleEvidence.objects.get_or_create(
                    roster_entry=entry, platform='x', handle__iexact=handle,
                    defaults={'handle': handle, 'evidence_url': entry.profile_url or entry.source_url, 'extracted_url': url})
                if created:
                    evidence.subject_content_type = ContentType.objects.get_for_model(entry, for_concrete_model=False)
                    evidence.subject_object_id = entry.pk
                    evidence.save(update_fields=['subject_content_type', 'subject_object_id'])
        self.stdout.write(f'Senat: osobistych kont X na profilach {personal}; odrzucone konta ze stopki strony: '
                          f'{", ".join(sorted(shared)) or "brak"}; nie udało się pobrać {failed} profili.')

    def _wikidata_mps(self, apply):
        """Posłowie z kontem X w Wikidanych, dopasowani do aktywnego składu Sejmu (tylko jednoznaczne nazwiska)."""
        import unicodedata
        query = """SELECT DISTINCT ?person ?personLabel ?x WHERE {
          ?person wdt:P39 wd:Q19269361 ; wdt:P2002 ?x .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "pl". } }"""
        try:
            rows = requests.get('https://query.wikidata.org/sparql', params={'query': query, 'format': 'json'}, timeout=90,
                                headers={'User-Agent': 'spin.clinic/1.0 (kontakt@spin.clinic)'}).json()['results']['bindings']
        except (requests.RequestException, ValueError, KeyError):
            self.stdout.write('Wikidane: nie udało się pobrać danych.')
            return

        def norm(value):
            return ' '.join(unicodedata.normalize('NFC', value).casefold().split())
        roster = {}
        for entry in ParliamentaryRosterEntry.objects.filter(source='sejm', active=True):
            roster.setdefault(norm(entry.full_name), []).append(entry)
        by_person = {}
        for row in rows:
            by_person.setdefault(row['person']['value'], (row['personLabel']['value'], set()))[1].add(row['x']['value'])
        matched = 0
        for person_url, (label, handles) in by_person.items():
            entries = roster.get(norm(label), [])
            if len(entries) != 1 or len(handles) != 1:
                continue  # brak w składzie, niejednoznaczne nazwisko albo kilka kont — pomijamy
            entry, handle = entries[0], next(iter(handles))
            if not re.fullmatch(r'[A-Za-z0-9_]{1,15}', handle):
                continue
            matched += 1
            camp = CLUB_CAMPS.get(entry.club)
            if not apply:
                self.stdout.write(f'{"POŁĄCZ " if camp else "POMIŃ  "} @{handle} → {entry.full_name} · Sejm · {entry.club or "klub nieustalony"}'
                                  + (f' · {camp}' if camp else '') + ' · Wikidane')
                self._senate_plan = getattr(self, '_senate_plan', 0) + (1 if camp else 0)
                continue
            evidence, created = SocialHandleEvidence.objects.get_or_create(
                roster_entry=entry, platform='x', handle__iexact=handle,
                defaults={'handle': handle, 'evidence_url': person_url, 'extracted_url': f'https://x.com/{handle}'})
            if created:
                evidence.subject_content_type = ContentType.objects.get_for_model(entry, for_concrete_model=False)
                evidence.subject_object_id = entry.pk
                evidence.save(update_fields=['subject_content_type', 'subject_object_id'])
        self.stdout.write(f'Wikidane: dopasowano {matched} posłów z kontem X.')
