"""Tygodnik legislacyjny - generator wersji roboczej (Kartograf, eksperyment Zarobek).

Tylko ODCZYT bazy (nic nie zapisuje, nic nie wysyła). Uruchamiany w kontenerze backendu:
    docker compose ... exec -T backend python manage.py shell < tygodnik.py > tygodnik_wynik.md
Ustawienia przez zmienne środowiskowe nie są potrzebne: okres = ostatnie 7 dni (DNI), wszystkie branże z BRANZE.

Wynik: statystyka (ile projektów w ruchu na branżę - dowód skali produktu) i wydanie dla każdej branży:
projekty zmienione w okresie, etap, nowe stanowiska z konsultacji, nowe zgłoszenia lobbingowe, linki do RCL.
Bez streszczeń treści (te dopiero po kontroli drugiego modelu) i bez nazw osób: autora zgłoszenia pokazujemy tylko,
gdy nazwa wygląda na organizację (ORG_SLOWA); inaczej „nazwa pominięta”.
"""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from news.models import LegislativeChange, LegislativeDocument, LegislativeProject
from scraper.rcl_guard import PROCESSING_NOTE, SOURCE_LINE

DNI = 7
BRANZE = {
    'Finanse i podatki': ['podat', 'finans', 'budżet', 'bank', 'rachunkow', 'vat', 'akcyz', 'ubezpiecz', 'kapitałow'],
    'Żywność i rolnictwo': ['żywno', 'rolni', 'rolny', 'weterynar', 'sanitarn', 'nawoz', 'rybo', 'pasz'],
    'Energetyka i klimat': ['energ', 'paliw', 'gaz', 'klimat', 'emisj', 'oze', 'ciepł', 'atom'],
    'Transport': ['transport', 'drog', 'kolej', 'lotni', 'morsk', 'pojazd', 'kierowc'],
    'Zdrowie i farmacja': ['zdrow', 'lecz', 'lek', 'farmac', 'medycz', 'szpital', 'apte'],
    'Budownictwo i nieruchomości': ['budowl', 'budown', 'nieruchom', 'planowan', 'mieszka', 'lokal'],
    'Praca i HR': ['pracy', 'pracown', 'wynagrodz', 'zatrudn', 'emerytur', 'zus', 'społeczn'],
    'Cyfryzacja i dane': ['cyfr', 'informaty', 'danych', 'elektroniczn', 'telekomun', 'cyberbezp', 'sztucznej intelig'],
    'Handel i konsumenci': ['handl', 'konsument', 'opakowa', 'odpad', 'reklam', 'sprzedaż'],
}
ORG_SLOWA = ('fundacj', 'stowarzysz', 'izba', 'izby', 'związek', 'zwiazek', 'federacj', 'konfederacj', 'polsk', 'krajow',
             'rada', 'instytut', 'sp. z o', 'spółka', 's.a.', 'sa ', 'kancelari', 'pracodawc', 'urząd', 'minister',
             'uniwersytet', 'akademi', 'ogólnopolsk', 'organizacj', 'grupa', 'forum', 'bank', 'samorząd', 'naczeln')


def tekst_projektu(p):
    return ' '.join([p.title or ''] + [str(x) for x in (p.departments or [])] + [str(x) for x in (p.keywords or [])]).lower()


def branze_projektu(p):
    t = tekst_projektu(p)
    return [b for b, slowa in BRANZE.items() if any(s in t for s in slowa)]


def autor(nazwa):
    n = (nazwa or '').strip()
    return n if n and any(s in n.lower() for s in ORG_SLOWA) else 'nazwa pominięta (możliwa osoba)'


def etap(p):
    st = [s for s in p.stages.all() if s.state in ('active', 'reached')]
    if not st:
        return 'b.d.'
    s = max(st, key=lambda s: (s.number or 0))
    return f'{s.number}. {s.name}' if s.number else s.name


def url(p):
    return p.source_url or LegislativeProject.url_for(p.rcl_id)


teraz = timezone.now()
od = teraz - timedelta(days=DNI)
zmienione_id = set(LegislativeChange.objects.filter(detected_at__gte=od).values_list('project_id', flat=True))
w_ruchu = list(LegislativeProject.objects.filter(Q(id__in=zmienione_id) | Q(list_modified_on__gte=od.date()))
               .prefetch_related('stages').order_by('-list_modified_on', '-rcl_id'))
nowe_docs = (LegislativeDocument.objects.filter(first_seen_at__gte=od, project__in=w_ruchu)
             .filter(category__in=['position', 'lobbying', 'comment_table']).select_related('project'))
docs_po_proj = {}
for d in nowe_docs:
    docs_po_proj.setdefault(d.project_id, []).append(d)

przypisane = {b: [] for b in BRANZE}
bez_branzy = 0
for p in w_ruchu:
    bs = branze_projektu(p)
    bez_branzy += not bs
    for b in bs:
        przypisane[b].append(p)

out = []
out.append(f'# Tygodnik legislacyjny - WERSJA ROBOCZA ({od:%d.%m}-{teraz:%d.%m.%Y})\n')
out.append(f'Baza: {LegislativeProject.objects.count()} projektów; w ruchu w okresie: {len(w_ruchu)}; '
           f'bez przypisanej branży: {bez_branzy}.\n')
out.append('| Branża | Projekty w ruchu | Nowe stanowiska z konsultacji | Nowe zgłoszenia lobbingowe |\n|---|---|---|---|')
for b, ps in przypisane.items():
    ds = [d for p in ps for d in docs_po_proj.get(p.id, [])]
    out.append(f'| {b} | {len(ps)} | {sum(d.category == "position" for d in ds)} | {sum(d.category == "lobbying" for d in ds)} |')

for b, ps in przypisane.items():
    if not ps:
        continue
    out.append(f'\n## {b}\n')
    for p in ps[:15]:
        nr = f' ({p.wykaz_number})' if p.wykaz_number else ''
        out.append(f'- **{p.title}**{nr} - {p.applicant or "wnioskodawca b.d."}; etap: {etap(p)}; '
                   f'zmiana na liście: {p.list_modified_on or "b.d."}. [RCL]({url(p)})')
        for d in docs_po_proj.get(p.id, [])[:8]:
            rodzaj = {'position': 'stanowisko', 'lobbying': 'zgłoszenie lobbingowe', 'comment_table': 'tabela uwag'}[d.category]
            out.append(f'  - nowe: {rodzaj} - {autor(d.author)} ({d.created_on or "b.d."}) [plik]({d.file_url})')
    if len(ps) > 15:
        out.append(f'- ... i {len(ps) - 15} kolejnych')

out.append(f'\n---\n{SOURCE_LINE}. {PROCESSING_NOTE} To przegląd informacyjny, nie porada prawna. '
           'Brak pozycji oznacza brak w naszych danych na dzień pobrania, nie brak w RCL.')
print('\n'.join(out))
