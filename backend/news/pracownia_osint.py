"""Pracownia OSINT przeszłość.today (właściciel 5.10): agenci, którzy rozwijają narzędzie dla dziennikarzy śledczych.

Cel: przeszłość.today ma być pierwszym wyborem dziennikarza do OSINT o życiu publicznym w Polsce: wszystko, co ma konkurencja,
i więcej, w pełni legalnie, prosto i czytelnie. Agenci tylko proponują; kod piszą Claude i Codex po zgodzie właściciela.

Sześć ról (każda z drugim modelem innej firmy do sprawdzenia, poza Kontrolerem, który liczy bez AI):
- Kartograf: co tydzień czyta nowości z branży OSINT i dziennikarstwa danych (GIJN, Bellingcat, OCCRP, OpenSanctions, ICIJ,
  Aleph, LittleSis i inne) i porównuje z katalogiem funkcji (FEATURES): czego nam brakuje.
- Zwiadowca: co tydzień przeszukuje katalog dane.gov.pl (oficjalne API) i listę rejestrów publicznych: nowe legalne zbiory danych.
- Prawnik: każdą propozycję Kartografa i Zwiadowcy ocenia według zasad (LEGAL): dozwolone, warunkowo albo niedozwolone.
- Dziennikarz testowy: dwa razy w tygodniu trzy osoby (śledczy, dziennikarz danych, fact-checker) wykonują prawdziwe zadania
  na tematach dnia i piszą, czego nie dało się ustalić.
- Kontroler danych: codziennie bez AI sprawdza świeżość i pokrycie danych (artykuły, wpisy, dokumenty, głosowania, KRS).
- Architekt: co tydzień łączy wszystko w plan: 10 następnych funkcji z poziomem (darmowe/Pro), wysiłkiem, stanem prawnym,
  kryteriami odbioru i gotowym zleceniem dla wykonawcy. Każda pozycja trafia do panelu jako pomysł (ocenia ją też Seba).
- Wynalazca (właściciel 5.10: „agent od kreatywności”): co 3 dni wymyśla nowe funkcje, których nie ma konkurencja,
  wyłącznie z danych, które już zbieramy (spis INVENTORY i liczby z bazy), na bazie katalogu i planu Architekta.
  Drugi model odrzuca pomysły bez danych, powielone albo zwykłe; Prawnik ocenia resztę, Architekt bierze najlepsze do planu.
- Technolog (właściciel 5.10: „badać nowe technologie i przyłączać je”): co tydzień czyta wydania otwartych narzędzi OSINT,
  danych i NLP (TECH_FEEDS) i proponuje, co podłączyć; licencja i bezpieczeństwo do sprawdzenia przez Claude przed instalacją.

Pętla (właściciel 5.10): badacze (Kartograf, Zwiadowca, Wynalazca, Technolog) -> Prawnik -> Architekt (plan i zlecenia)
-> budowa (Claude i Codex) -> strażnicy (testy, Recenzent, Projektant, Dziennikarz testowy, Kontroler) -> wdrożenie -> badacze."""
import re
from datetime import timedelta

import requests
from django.db.models import Max
from django.utils import timezone

from news import agents_common as common
from news.agent_models import AgentNote

AGENTS = ('kartograf', 'zwiadowca', 'prawnik', 'dziennikarz', 'kontroler', 'architekt', 'wynalazca', 'technolog')
EVERY = {'technolog': timedelta(days=6), 'wynalazca': timedelta(days=3), 'kartograf': timedelta(days=6), 'zwiadowca': timedelta(days=6), 'architekt': timedelta(days=6),
         'dziennikarz': timedelta(days=3), 'kontroler': timedelta(hours=20)}
UA = {'User-Agent': 'przeszlosc.today Pracownia OSINT (+https://spin.clinic)'}

# Katalog funkcji: stan u nas wobec konkurencji. Agenci go czytają, Architekt proponuje zmiany statusów.
# status: jest / częściowo / brak; tier: darmowe / Pro.
FEATURES = [
    ('temat', 'Temat jako drzewo powiązań: osoby, spółki, dokumenty, wpisy, artykuły', 'LittleSis, Maltego, Aleph', 'jest', 'darmowe'),
    ('os-czasu', 'Oś czasu tematu dzień po dniu ze źródłem przy każdym wpisie', 'Aleph, Maltego, Pinpoint', 'jest', 'darmowe'),
    ('bilans-mediow', 'Rozkład źródeł medialnych w temacie', 'Media Cloud', 'jest', 'darmowe'),
    ('spin', 'Analiza spinu wypowiedzi (Dr. Spin) z siłą, chwytami i sprawdzeniem', 'brak u konkurencji', 'jest', 'darmowe'),
    ('przekaz-obozow', 'Porównanie przekazu rządzących i opozycji tego samego dnia', 'brak u konkurencji', 'jest', 'darmowe'),
    ('cytowanie', 'Każdy fakt z linkiem do oryginału i datą', 'Aleph, OpenSanctions', 'jest', 'darmowe'),
    ('profil-osoby', 'Profil osoby: funkcje, wypowiedzi z diagnozami, głosowania, powiązania', 'TheyWorkForYou, LittleSis, sejm-stats', 'częściowo', 'darmowe'),
    ('krs-historia', 'Funkcje osób publicznych w KRS z historią (od kiedy, do kiedy)', 'rejestr.io, OpenCorporates', 'częściowo', 'Pro'),
    ('graf-2-stopnie', 'Graf powiązań osoba - spółka - osoba (dwa stopnie) z wyjaśnieniem każdej krawędzi', 'rejestr.io, Maltego, Aleph, Sayari', 'brak', 'Pro'),
    ('glosowania-imienne', 'Głosowania imienne w temacie: kluby zbiorczo, posłowie po rozwinięciu', 'sejm-stats, mojepanstwo, TheyWorkForYou', 'częściowo', 'darmowe'),
    ('sciezka-ustawy', 'Ścieżka ustawy: druki, poprawki (kto zgłosił), wersje, głosowania, podpis', 'Legislative Observatory, mojepanstwo', 'częściowo', 'darmowe'),
    ('lobbing', 'Rejestr lobbingu i zgłoszenia w uzasadnieniach projektów przy temacie', 'LobbyFacts, Transparency Register', 'częściowo', 'Pro'),
    ('zamowienia', 'Zamówienia publiczne (e-Zamówienia, TED) przy spółkach z tematu', 'opentender.eu, Sayari, rejestr.io', 'brak', 'Pro'),
    ('umowy-cru', 'Centralny rejestr umów jednostek publicznych', 'CRU (MF)', 'brak', 'Pro'),
    ('dotacje-ue', 'Beneficjenci funduszy UE i dotacji krajowych przy spółkach', 'Kohesio, FTS, mapadotacji', 'brak', 'Pro'),
    ('oswiadczenia', 'Oświadczenia majątkowe posłów i ministrów: zmiany rok do roku', 'TheyWorkForYou (register of interests)', 'brak', 'Pro'),
    ('finanse-partii', 'Sprawozdania finansowe partii i komitetów (PKW)', 'OpenSecrets, PKW', 'brak', 'darmowe'),
    ('reklamy-polityczne', 'Reklamy polityczne z oficjalnej biblioteki reklam Meta (API)', 'Meta Ad Library, Who Targets Me', 'brak', 'Pro'),
    ('sankcje-pep', 'Sprawdzenie listy sankcyjnej przy spółkach (źródła urzędowe UE/ONZ/MSWiA)', 'OpenSanctions, Sayari', 'brak', 'Pro'),
    ('watchdog', 'Strażnik zmian: ciche poprawki i usunięcia cytowanych artykułów', 'NewsDiffs, Wayback', 'brak', 'Pro'),
    ('archiwum-jednym', 'Utrwalenie źródła jednym kliknięciem (archive.org Save Page Now) z datą', 'Hunchly, archive.today', 'brak', 'Pro'),
    ('alerty', 'Alerty: nowy wpis, dokument, głosowanie albo funkcja w KRS obserwowanej osoby lub tematu', 'Aleph, rejestr.io, Newspoint', 'brak', 'Pro'),
    ('eksport', 'Eksport tematu do CSV, JSON i PDF z przypisami źródeł', 'Aleph, Maltego', 'częściowo', 'Pro'),
    ('api', 'API dla redakcji (klucz, limity, dokumentacja)', 'Aleph, OpenSanctions', 'brak', 'Pro'),
    ('szukanie-filtry', 'Wyszukiwanie z filtrami: data, rodzaj, osoba, obóz, źródło', 'Aleph, Datashare, Pinpoint', 'częściowo', 'darmowe'),
    ('teczka', 'Teczka dochodzenia: zapisane tematy, przypięte dowody, notatki', 'Aleph, Hunchly, Maltego', 'brak', 'Pro'),
    ('zespol', 'Wspólna teczka zespołu redakcji z uprawnieniami', 'Aleph, Maltego', 'brak', 'Pro'),
    ('wlasne-dokumenty', 'Własne dokumenty dziennikarza: wyszukiwanie osób i firm, prywatnie, bez udostępniania', 'Datashare, Pinpoint, Aleph', 'brak', 'Pro'),
    ('wywiady', 'Transkrypcje wywiadów z wyszukiwaniem po wypowiedziach', 'Pinpoint', 'częściowo', 'darmowe'),
    ('narracje', 'Wykrywanie skoordynowanych narracji: te same frazy w wielu kontach publicznych w krótkim czasie', 'Junkipedia, Meltwater', 'częściowo', 'Pro'),
    ('zmiana-zdania', 'Zmiana zdania w czasie: co ta sama osoba mówiła o temacie wcześniej', 'PolitiFact Flip-O-Meter, Demagog', 'brak', 'darmowe'),
    ('fact-checki', 'Werdykty innych fact-checkerów przy twierdzeniu (Google Fact Check Tools API)', 'Google Fact Check Explorer', 'brak', 'darmowe'),
    ('okregi', 'Mapa: okręgi wyborcze posłów i regionalne wątki', 'TheyWorkForYou', 'brak', 'darmowe'),
    ('beneficjenci', 'Beneficjenci rzeczywiści (CRBR, oficjalne API) przy spółkach z tematu', 'Sayari, OpenOwnership', 'brak', 'Pro'),
    ('upadlosci', 'Krajowy Rejestr Zadłużonych i Monitor Sądowy przy spółkach', 'rejestr.io', 'brak', 'Pro'),
    ('przeplyw-pieniedzy', 'Przepływ pieniędzy: dotacje i zamówienia do spółek i osób z tematu', 'Sayari, Follow the Money', 'brak', 'Pro'),
    ('format-ftm', 'Eksport w formacie FollowTheMoney (zgodny z Aleph)', 'Aleph, OpenSanctions', 'brak', 'Pro'),
    ('spinki-kontekstowe', 'Spinki kontekstowe dla dziennikarzy: łańcuch materiałów z uzasadnieniem połączeń', 'brak u konkurencji', 'częściowo', 'Pro'),
]
# Zasady Prawnika: legalność ponad wszystko (właściciel 5.10: „w pełni legalne narzędzie”).
LEGAL = [
    'Tylko dane publiczne z oficjalnych źródeł (rejestry, API urzędów, BIP, Sejm, ELI, dane.gov.pl) albo publikacje medialne jako link i krótki cytat.',
    'Bez obchodzenia logowania, płatnych murów, CAPTCHA i blokad; bez scrapowania serwisów, których regulamin tego zabrania; X tylko przez oficjalne API.',
    'Osoby: tylko osoby publiczne w związku z działalnością publiczną (RODO art. 6 ust. 1 lit. e/f i art. 85, prawo prasowe art. 14 ust. 6); osoby prywatne nie są profilowane ani wyszukiwane.',
    'Bez danych szczególnych kategorii (zdrowie, wyznanie, orientacja, poglądy osób prywatnych) i bez danych o wyrokach poza jawnymi orzeczeniami wobec osób publicznych.',
    'Licencja zbioru musi pozwalać na ponowne wykorzystanie także komercyjne (ustawa o otwartych danych); CC BY-NC tylko po wykupieniu licencji.',
    'Pełne teksty artykułów nie są przechowywane ani udostępniane; tylko metadane, link, krótki cytat i skrót zmian.',
    'Każdy fakt ze źródłem i datą; powiązanie z KRS jako kontekst osoby, nie dowód winy; prawo do sprostowania i rejestr korekt.',
    'Ta sama miara dla wszystkich stron sceny politycznej; żadna funkcja nie jest budowana pod jedną partię ani pod zamówienie rządu.',
    'Własne dokumenty dziennikarza tylko prywatnie w jego koncie, szyfrowane, usuwalne, nigdy nie mieszane z bazą publiczną.',
]
FEEDS = {
    'GIJN': 'https://gijn.org/feed/',
    'Bellingcat': 'https://www.bellingcat.com/feed/',
    'OCCRP': 'https://www.occrp.org/en/feed',
    'ICIJ': 'https://www.icij.org/feed/',
    'OpenSanctions': 'https://www.opensanctions.org/articles/rss/',
    'Aleph (wydania)': 'https://github.com/alephdata/aleph/releases.atom',
    'Datashare (wydania)': 'https://github.com/ICIJ/datashare/releases.atom',
    'Nieman Lab': 'https://www.niemanlab.org/feed/',
    'Journalism.co.uk': 'https://www.journalism.co.uk/feed/',
    'First Draft / Information Futures Lab': 'https://firstdraftnews.org/feed/',
}
TECH_FEEDS = {
    'FollowTheMoney (format danych OSINT)': 'https://github.com/alephdata/followthemoney/releases.atom',
    'OpenSanctions yente (dopasowanie podmiotów)': 'https://github.com/opensanctions/yente/releases.atom',
    'Datashare (ICIJ)': 'https://github.com/ICIJ/datashare/releases.atom',
    'spaCy (rozpoznawanie nazw)': 'https://github.com/explosion/spaCy/releases.atom',
    'Datasette (publikacja danych)': 'https://github.com/simonw/datasette/releases.atom',
    'MapLibre (mapy)': 'https://github.com/maplibre/maplibre-gl-js/releases.atom',
    'Sigma.js (grafy)': 'https://github.com/jacomyal/sigma.js/releases.atom',
    'Hugging Face (modele)': 'https://huggingface.co/blog/feed.xml',
    'Simon Willison (narzędzia danych i AI)': 'https://simonwillison.net/atom/everything/',
}
DATA_QUERIES = ['krs', 'zamówienia publiczne', 'dotacje', 'umowy', 'oświadczenia majątkowe', 'lobbing', 'partie polityczne',
                'subwencje', 'beneficjenci', 'spółki skarbu państwa', 'fundusze europejskie', 'wybory', 'posłowie', 'rejestr',
                'nieruchomości skarbu państwa', 'kontrole NIK']
PERSONAS = {
    'śledczy': 'Dziennikarz śledczy dużej redakcji. Zadanie: kto z osób publicznych w temacie „{t}” ma funkcje w spółkach, '
               'czy te spółki dostały pieniądze publiczne i kto o temacie mówił najgłośniej.',
    'dziennikarz danych': 'Dziennikarz danych. Zadanie: jak głosowały kluby w sprawie „{t}”, co politycy mówili przed głosowaniem '
                          'i czy da się to pobrać jako tabelę.',
    'fact-checker': 'Fact-checker lokalnego portalu. Zadanie: które twierdzenia o „{t}” zostały sprawdzone, co jest prawdą, '
                    'skąd to wiadomo i czy ktoś zmienił zdanie w czasie.',
}

# Co zbieramy (Wynalazca łączy te źródła w nowe funkcje; liczby dokłada inventory()).
INVENTORY = [
    'Wpisy polityków z X (oficjalne API), z kontem, partią i obozem osoby',
    'Diagnozy Dr. Spina: siła spinu 0-100, chwyty i rodziny technik, sprawdzone twierdzenia ze źródłami, oceny 4 modeli Konsylium',
    'Przekazy dnia: teza rządzących i opozycji tego samego dnia, analiza, wymówki stron',
    'Wywiady dnia: transkrypcje rozmów polityków (YouTube), diagnoza gościa i prowadzącego',
    'Artykuły z RSS ok. 75 redakcji (metadane, tytuł, data, link, kategoria), ponad pół miliona rekordów',
    'Sejm: druki, projekty, poprawki, głosowania z głosami imiennymi posłów, posiedzenia (API Sejmu, ELI)',
    'Dokumenty urzędów: KPRM, MSWiA, Ministerstwo Finansów, inne instytucje (metadane z gov.pl i BIP)',
    'KRS: potwierdzone funkcje osób publicznych w spółkach, fundacjach i stowarzyszeniach',
    'Rejestr osób publicznych: posłowie, senatorowie, ministrowie, europosłowie, role i partie',
    'Spinki: łańcuchy materiałów z typami połączeń i ocenami czytelników, przepięcia, komentarze',
    'Sygnały lobbingu: zgłoszenia w uzasadnieniach projektów i konsultacje',
    'Archiwa: kopie archive.org i dostępność źródeł w czasie (czy link zniknął)',
    'Zbiorcze ścieżki czytelników po serwisie (bez danych osobowych)',
]
TEXT = {'type': 'string'}
INT = {'type': 'integer'}
LIST = {'type': 'array', 'items': TEXT}
GAP = {'type': 'object', 'properties': {'feature': TEXT, 'who_has': TEXT, 'why_journalists_care': TEXT, 'source_url': TEXT,
       'catalog_id': TEXT}, 'required': ['feature', 'who_has', 'why_journalists_care', 'source_url']}
GAPS_SCHEMA = {'type': 'object', 'properties': {'summary': TEXT, 'gaps': {'type': 'array', 'items': GAP}}, 'required': ['summary', 'gaps']}
SOURCE = {'type': 'object', 'properties': {'dataset': TEXT, 'url': TEXT, 'license': TEXT, 'use': TEXT, 'feature': TEXT,
          'value': INT}, 'required': ['dataset', 'url', 'license', 'use', 'value']}
SOURCES_SCHEMA = {'type': 'object', 'properties': {'summary': TEXT, 'sources': {'type': 'array', 'items': SOURCE}},
                  'required': ['summary', 'sources']}
CHECK_SCHEMA = {'type': 'object', 'properties': {'remove': {'type': 'array', 'items': INT}, 'reason': TEXT}, 'required': ['remove', 'reason']}
VERDICT = {'type': 'object', 'properties': {'n': INT, 'verdict': {'type': 'string', 'enum': ['dozwolone', 'warunkowo', 'niedozwolone']},
           'why': TEXT, 'conditions': TEXT}, 'required': ['n', 'verdict', 'why']}
LEGAL_SCHEMA = {'type': 'object', 'properties': {'verdicts': {'type': 'array', 'items': VERDICT}}, 'required': ['verdicts']}
TEST_SCHEMA = {'type': 'object', 'properties': {'score': INT, 'answered': TEXT, 'missing': LIST, 'friction': LIST, 'wish': TEXT},
               'required': ['score', 'answered', 'missing', 'friction', 'wish']}
ITEM = {'type': 'object', 'properties': {
    'title': TEXT, 'catalog_id': TEXT, 'tier': {'type': 'string', 'enum': ['darmowe', 'Pro']},
    'effort': {'type': 'string', 'enum': ['S', 'M', 'L']}, 'value': INT, 'why': TEXT, 'acceptance': LIST, 'brief': TEXT},
    'required': ['title', 'tier', 'effort', 'value', 'why', 'acceptance', 'brief']}
PLAN_SCHEMA = {'type': 'object', 'properties': {'summary': TEXT, 'items': {'type': 'array', 'items': ITEM}}, 'required': ['summary', 'items']}

MISSION = ('Pracujesz w Pracowni OSINT przeszłość.today: narzędzia, które ma być pierwszym wyborem dziennikarzy w Polsce do badania życia '
           'publicznego (osoby publiczne, spółki, ustawy, głosowania, pieniądze publiczne, przekaz w mediach). Musi mieć wszystko, co '
           'konkurencja, i więcej, być w pełni legalne oraz pokazywać dane prosto i czytelnie. Płatne funkcje Pro dla dziennikarzy, '
           'podstawy darmowe. Ta sama miara dla wszystkich stron polityki. Piszesz po polsku, konkretnie, bez ogólników.')
KARTOGRAF = (MISSION + ' Jesteś Kartografem. Na podstawie WYŁĄCZNIE items (nowości z branży OSINT i dziennikarstwa danych) oraz katalogu '
             'funkcji (catalog: id, funkcja, kto ma, nasz status) wypisz do 8 luk: funkcji lub sposobów pracy, które dziennikarze cenią, '
             'a których u nas brak albo są częściowe. source_url musi pochodzić z items; catalog_id z katalogu, jeśli pasuje.')
KARTOGRAF_CHECK = ('Sprawdź luki kolegi. W remove podaj numery (od 0) luk bez pokrycia w items, już obecnych w katalogu jako „jest” '
                   'albo nieprzydatnych dziennikarzom badającym życie publiczne w Polsce.')
ZWIADOWCA = (MISSION + ' Jesteś Zwiadowcą danych. Z datasets (katalog dane.gov.pl: tytuł, licencja, aktualizacja, link) wybierz do 8 '
             'zbiorów, które najbardziej wzbogacą narzędzie. Dla każdego: do czego użyć (use), którą funkcję katalogu wspiera (feature), '
             'licencja dokładnie z danych, wartość 1-10. Pomijaj zbiory nieaktualizowane od lat i bez związku z życiem publicznym.')
ZWIADOWCA_CHECK = ('Sprawdź wybór kolegi. W remove podaj numery (od 0) zbiorów spoza datasets, z licencją inną niż w danych '
                   'albo bez związku z badaniem życia publicznego.')
PRAWNIK = ('Jesteś Prawnikiem Pracowni OSINT (prawo polskie i UE: RODO, prawo prasowe, ustawa o otwartych danych, prawo autorskie, '
           'regulaminy serwisów). Oceń każdą propozycję (proposals, numer n) według zasad (rules). Werdykt: dozwolone, warunkowo '
           '(podaj warunki) albo niedozwolone (podaj dlaczego). Bądź ostrożny: w razie wątpliwości warunkowo z konsultacją prawnika.')
DZIENNIKARZ = ('Jesteś dziennikarzem testującym narzędzie OSINT ({persona}). {task} Masz tylko to, co narzędzie zwróciło (result). '
               'Oceń 1-10, na ile udało się wykonać zadanie (score), co ustaliłeś (answered), czego zabrakło (missing: konkretne dane '
               'lub funkcje), co przeszkadzało (friction) i jedną najważniejszą prośbę (wish). Nie zmyślaj faktów spoza result.')
TECH = {'type': 'object', 'properties': {'tool': TEXT, 'what': TEXT, 'use_here': TEXT, 'feature': TEXT, 'license': TEXT,
        'effort': {'type': 'string', 'enum': ['S', 'M', 'L']}, 'value': INT, 'source_url': TEXT},
        'required': ['tool', 'what', 'use_here', 'license', 'effort', 'value', 'source_url']}
TECH_SCHEMA = {'type': 'object', 'properties': {'summary': TEXT, 'tech': {'type': 'array', 'items': TECH}}, 'required': ['summary', 'tech']}
TECHNOLOG = (MISSION + ' Jesteś Technologiem. Z items (wydania i wpisy o otwartych narzędziach) wybierz do 6 technologii, które warto '
             'podłączyć do przeszłość.today: co to jest, gdzie u nas pomoże (use_here, funkcja z katalogu), licencja (jeśli nieznana, napisz '
             '„do sprawdzenia”), wysiłek S/M/L, wartość 1-10, source_url z items. Tylko otwarte i darmowe; nic, co wysyła dane osób na zewnątrz.')
TECHNOLOG_CHECK = ('Sprawdź wybór kolegi. W remove podaj numery (od 0) pozycji bez pokrycia w items, płatnych, zamkniętych, '
                   'niepotrzebnych przy obecnych funkcjach albo ryzykownych dla prywatności.')
IDEA = {'type': 'object', 'properties': {'title': TEXT, 'what': TEXT, 'why_unique': TEXT, 'data_used': LIST, 'example': TEXT,
        'tier': {'type': 'string', 'enum': ['darmowe', 'Pro']}, 'wow': INT, 'risk': TEXT},
        'required': ['title', 'what', 'why_unique', 'data_used', 'example', 'tier', 'wow']}
IDEAS_SCHEMA = {'type': 'object', 'properties': {'summary': TEXT, 'ideas': {'type': 'array', 'items': IDEA}}, 'required': ['summary', 'ideas']}
WYNALAZCA = (MISSION + ' Jesteś Wynalazcą: najbardziej kreatywnym członkiem zespołu. Wymyśl do 10 NOWYCH funkcji, których nie ma żadna '
             'konkurencja i które sprawią, że dziennikarz wybierze nas, a nie Aleph, rejestr.io czy Maltego. Łącz nasze źródła (inventory) '
             'w sposób, jakiego nikt nie robi: przekaz + głosowania + KRS + media + spin + czas. Myśl odważnie: wskaźniki, porównania, '
             'wykrywanie wzorców, prognozy, formaty dla czytelników, narzędzia dla redakcji, sposoby pokazania prawdy prosto. '
             'Warunki: tylko dane z inventory (data_used to pozycje z inventory), legalnie, ta sama miara dla wszystkich stron, bez '
             'profilowania osób prywatnych. Nie powtarzaj funkcji z katalogu (catalog) ani wcześniejszych pomysłów (previous). Dla każdej: '
             'tytuł, co robi, dlaczego nikt tego nie ma, przykład na prawdziwym temacie z topics, poziom, efekt wow 1-10, ryzyko.')
WYNALAZCA_CHECK = ('Sprawdź pomysły kolegi. W remove podaj numery (od 0) pomysłów: wymagających danych spoza inventory, powielających '
                   'katalog lub previous, zwykłych (konkurencja już to ma), naruszających zasadę tej samej miary albo profilujących osoby prywatne.')
ARCHITEKT = (MISSION + ' Jesteś Architektem produktu. Masz katalog funkcji, luki Kartografa, pomysły Wynalazcy (ideas), technologie Technologa (tech), zbiory Zwiadowcy z werdyktami Prawnika, '
             'raporty dziennikarzy testowych i stan danych Kontrolera. Ułóż plan 10 następnych funkcji, od najważniejszej. Tylko '
             'propozycje dozwolone lub warunkowe (z warunkami w brief), pomijasz „do konsultacji” i niedozwolone. Dla każdej: tytuł, catalog_id, poziom (darmowe/Pro), wysiłek '
             'S/M/L, wartość 1-10, dlaczego (z odwołaniem do konkretnego raportu), 3-5 kryteriów odbioru i brief: gotowe zlecenie dla '
             'programisty (co zbudować, z jakich danych, jak pokazać prosto). Najpierw to, co przyciągnie dziennikarzy najszybciej.')
ARCHITEKT_CHECK = ('Sprawdź plan kolegi. W remove podaj numery (od 0) pozycji niedozwolonych prawnie, bez oparcia w raportach, '
                   'powielających funkcję o statusie „jest” albo łamiących zasadę tej samej miary.')

_used = {'author': None, 'checker': None}


def _ask(prompt, data, schema, force, checker=False):
    exclude = tuple(m for m in [_used['author']] if m) if checker else ()
    answer, member = common.ask_any(prompt, data, schema, force, exclude=exclude)
    _used['checker' if checker else 'author'] = member
    return answer


def _authors():
    return [':'.join(_used['author'] or ('-',)), ':'.join(_used['checker'] or ('-',))]


def _drop(rows, verdict):
    drop = {int(x) for x in verdict.get('remove', []) if str(x).lstrip('-').isdigit()}
    return [r for n, r in enumerate(rows) if n not in drop]


def catalog():
    return [{'id': i, 'feature': f, 'who_has': w, 'status': s, 'tier': t} for i, f, w, s, t in FEATURES]


def _save(agent, kind, title, body, data, sources=(), notify=False):
    note = AgentNote.objects.create(agent=agent, kind=kind, status='new', title=title[:240], body=body, scores=data,
                                    sources=sorted(set(sources)))
    if notify:
        common.notify(note)
    return note


def _last(agent, kind=None):
    rows = AgentNote.objects.filter(agent=agent)
    return (rows.filter(kind=kind) if kind else rows).first()


# ---------- Kartograf ----------
def feed_items(limit=6, feeds=None):
    import feedparser
    items = []
    for name, url in (feeds or FEEDS).items():
        try:
            parsed = feedparser.parse(requests.get(url, timeout=15, headers=UA).content)
        except requests.RequestException:
            continue
        for entry in parsed.entries[:limit]:
            link = entry.get('link', '')
            if link.startswith('https://'):
                items.append({'source': name, 'title': entry.get('title', '')[:200], 'url': link,
                              'summary': re.sub(r'<[^>]+>', ' ', entry.get('summary', ''))[:400]})
    return items


def kartograf(force=False):
    items = feed_items()
    if not items:
        raise common.WindowClosed('Brak nowości ze źródeł branży OSINT.')
    urls = {i['url'] for i in items}
    answer = _ask(KARTOGRAF, {'items': items[:45], 'catalog': catalog()}, GAPS_SCHEMA, force)
    gaps = [g for g in answer.get('gaps', []) if isinstance(g, dict) and g.get('source_url') in urls]
    if gaps:
        gaps = _drop(gaps, _ask(KARTOGRAF_CHECK, {'items': items[:45], 'catalog': catalog(), 'gaps': gaps}, CHECK_SCHEMA, force, True))
    data = {'summary': answer.get('summary', ''), 'gaps': gaps, 'authors': _authors()}
    body = chr(10).join([data['summary'], ''] + [f"- {g['feature']} (mają: {g['who_has']}): {g['why_journalists_care']} ({g['source_url']})"
                                                for g in gaps]).strip()
    return _save('kartograf', 'finding', f'Luki wobec konkurencji: {timezone.localdate():%d.%m.%Y}', body, data,
                 [g['source_url'] for g in gaps])


# ---------- Zwiadowca ----------
def datasets(per_query=8):
    rows, seen = [], set()
    for query in DATA_QUERIES:
        try:
            data = requests.get('https://api.dane.gov.pl/1.4/datasets', params={'q': query, 'per_page': per_query, 'sort': '-modified'},
                                timeout=20, headers=UA).json()
        except (requests.RequestException, ValueError):
            continue
        for item in data.get('data', []):
            a = item.get('attributes', {})
            if item.get('id') in seen:
                continue
            seen.add(item.get('id'))
            rows.append({'title': (a.get('title') or '')[:200], 'url': (item.get('links') or {}).get('self', '').replace('api.dane.gov.pl/1.4', 'dane.gov.pl/pl'),
                         'license': a.get('license_name') or '', 'modified': (a.get('modified') or '')[:10],
                         'frequency': a.get('update_frequency') or '', 'source': ((a.get('source') or {}).get('title') if isinstance(a.get('source'), dict) else '') or '',
                         'query': query})
    return rows


def zwiadowca(force=False):
    rows = datasets()
    if not rows:
        raise common.WindowClosed('Katalog dane.gov.pl niedostępny.')
    known = {r['url']: r for r in rows}
    answer = _ask(ZWIADOWCA, {'datasets': rows[:90], 'catalog': catalog()}, SOURCES_SCHEMA, force)
    found = [s for s in answer.get('sources', []) if isinstance(s, dict) and s.get('url') in known]
    for s in found:
        s['license'] = known[s['url']]['license']  # licencja zawsze z katalogu, nie z modelu
    if found:
        found = _drop(found, _ask(ZWIADOWCA_CHECK, {'datasets': rows[:90], 'sources': found}, CHECK_SCHEMA, force, True))
    data = {'summary': answer.get('summary', ''), 'sources': found, 'authors': _authors()}
    body = chr(10).join([data['summary'], ''] + [f"- {s['dataset']} [{s['license']}] wartość {s['value']}/10: {s['use']} ({s['url']})"
                                                for s in found]).strip()
    return _save('zwiadowca', 'finding', f'Nowe zbiory danych: {timezone.localdate():%d.%m.%Y}', body, data, [s['url'] for s in found])


# ---------- Prawnik ----------
def prawnik(force=False):
    since = getattr(_last('prawnik', 'review'), 'created_at', None)
    notes = AgentNote.objects.filter(agent__in=['kartograf', 'zwiadowca', 'wynalazca', 'technolog'], kind='finding')
    if since:
        notes = notes.filter(created_at__gt=since)
    proposals = []
    for note in notes[:20]:
        for g in (note.scores or {}).get('gaps', []):
            proposals.append({'note': note.pk, 'what': f"Funkcja: {g['feature']} ({g.get('why_journalists_care', '')})"})
        for t in (note.scores or {}).get('tech', []):
            proposals.append({'note': note.pk, 'what': f"Technologia: {t['tool']}, licencja {t['license']}, użycie: {t['use_here']}"})
        for i in (note.scores or {}).get('ideas', []):
            proposals.append({'note': note.pk, 'what': f"Pomysł: {i['title']} ({i['what']}; dane: {', '.join(i.get('data_used', []))})"})
        for s in (note.scores or {}).get('sources', []):
            proposals.append({'note': note.pk, 'what': f"Zbiór: {s['dataset']}, licencja {s['license']}, użycie: {s['use']}"})
    if not proposals:
        return None
    proposals = [{'n': n, **p} for n, p in enumerate(proposals[:60])]
    answer = _ask(PRAWNIK, {'rules': LEGAL, 'proposals': proposals}, LEGAL_SCHEMA, force)
    verdicts = {v['n']: v for v in answer.get('verdicts', []) if isinstance(v, dict) and isinstance(v.get('n'), int)}
    rows = [{**p, 'verdict': verdicts.get(p['n'], {}).get('verdict', 'do konsultacji'), 'why': verdicts.get(p['n'], {}).get('why', 'brak oceny: do konsultacji'),
             'conditions': verdicts.get(p['n'], {}).get('conditions', '')} for p in proposals]
    data = {'verdicts': rows, 'authors': _authors()}
    body = chr(10).join(f"[{r['verdict']}] {r['what']}: {r['why']}{(' Warunki: ' + r['conditions']) if r['conditions'] else ''}" for r in rows)
    return _save('prawnik', 'review', f"Ocena prawna: {len(rows)} propozycji, {sum(r['verdict'] == 'niedozwolone' for r in rows)} odrzuconych",
                 body, data)


# ---------- Dziennikarz testowy ----------
def _digest(graph):
    """Co narzędzie zwróciło, w skrócie dla testera (bez całych tekstów)."""
    nodes = graph.get('nodes', [])
    people = [n for n in nodes if n.get('kind') == 'person'][:10]
    orgs = [n for n in nodes if n.get('kind') == 'organisation']
    events = sorted([n for n in nodes if n.get('date') and n.get('kind') in ('statement', 'record', 'media', 'diagnosis')],
                    key=lambda n: n.get('date') or '', reverse=True)[:14]
    return {'counts': graph.get('counts', {}), 'people': [{'name': p.get('label'), 'role': p.get('role', ''), 'camp': p.get('camp', ''),
            'links': p.get('links', 0)} for p in people], 'organisations': [o.get('label') for o in orgs[:10]],
            'events': [{'date': e.get('date'), 'kind': e.get('kind'), 'text': (e.get('label') or '')[:160]} for e in events],
            'features_available': ['oś czasu', 'kto występuje z funkcjami w KRS', 'rozkład źródeł medialnych', 'diagnozy Dr. Spina']}


def dziennikarz(force=False):
    from news import przeszlosc
    topics = [t['topic'] for t in przeszlosc.auto_topics()][:3] or ['CPK']
    tests = []
    for (persona, task), topic in zip(PERSONAS.items(), topics * 3):
        graph = przeszlosc.topic_graph(topic)
        result = _digest(graph)
        answer = _ask(DZIENNIKARZ.format(persona=persona, task=task.format(t=topic)), {'result': result}, TEST_SCHEMA, force)
        tests.append({'persona': persona, 'topic': topic, 'counts': result['counts'], 'score': max(1, min(10, int(answer.get('score') or 1))),
                      'answered': answer.get('answered', ''), 'missing': answer.get('missing', [])[:6],
                      'friction': answer.get('friction', [])[:4], 'wish': answer.get('wish', '')})
    data = {'tests': tests, 'authors': _authors()}
    body = chr(10).join(f"{t['persona']} · {t['topic']}: {t['score']}/10{chr(10)}  Ustalił: {t['answered']}{chr(10)}"
                        f"  Brakowało: {'; '.join(t['missing'])}{chr(10)}  Prośba: {t['wish']}" for t in tests)
    avg = sum(t['score'] for t in tests) / max(1, len(tests))
    return _save('dziennikarz', 'review', f'Testy dziennikarskie: średnio {avg:.1f}/10', body, data)


# ---------- Kontroler danych (bez AI) ----------
def kontroler(force=False):
    from news.models import Article, Ballot, ParliamentaryVoting
    from news.political_models import PoliticalPost, PublicFigure, PublicFigureOrganisationRelation
    from news.public_records_models import PublicRecord
    now = timezone.now()
    rows, problems = [], []

    def fresh(label, model, field, max_days, count=True):
        latest = model.objects.aggregate(m=Max(field))['m']
        if latest is not None and not hasattr(latest, 'hour'):
            latest = timezone.make_aware(timezone.datetime.combine(latest, timezone.datetime.min.time()))
        age = (now - latest).days if latest else None
        total = model.objects.count() if count else None
        rows.append({'data': label, 'count': total, 'latest': latest.date().isoformat() if latest else None, 'age_days': age})
        if age is None or age > max_days:
            problems.append(f'{label}: ostatni wpis {"nigdy" if age is None else f"{age} dni temu"} (norma do {max_days} dni)')

    fresh('Artykuły', Article, 'created_at', 1)
    fresh('Wpisy polityków', PoliticalPost, 'published_at', 1)
    fresh('Dokumenty Sejmu i urzędów', PublicRecord, 'date', 7)
    fresh('Głosowania (artykuły głosowań)', ParliamentaryVoting, 'article__created_at', 14)
    ballots = Ballot.objects.count()
    rows.append({'data': 'Głosy imienne', 'count': ballots})
    if not ballots:
        problems.append('Brak głosów imiennych: funkcja „głosowania imienne” nie ma danych.')
    people = PublicFigure.objects.filter(archived=False)
    with_krs = PublicFigureOrganisationRelation.objects.filter(verification_status='confirmed').values('public_figure').distinct().count()
    rows.append({'data': 'Osoby publiczne', 'count': people.count(), 'with_confirmed_krs': with_krs})
    from news import przeszlosc
    empty = [t['topic'] for t in przeszlosc.auto_topics() if not (t.get('counts') or {}).get('record')]
    if empty:
        problems.append(f"Tematy dnia bez dokumentów Sejmu: {', '.join(empty)} (dopasowanie druków po przedmiocie ustawy).")
    data = {'rows': rows, 'problems': problems}
    body = chr(10).join([f"- {r['data']}: {r.get('count')}" + (f", ostatni {r['latest']}" if r.get('latest') else '') for r in rows]
                        + ([''] + ['Problemy:'] + [f'- {p}' for p in problems] if problems else ['', 'Bez problemów.']))
    return _save('kontroler', 'audit', f'Stan danych: {len(problems)} problemów', body, data)


# ---------- Technolog ----------
def technolog(force=False):
    items = feed_items(feeds=TECH_FEEDS, limit=4)
    if not items:
        raise common.WindowClosed('Brak wydań narzędzi do przejrzenia.')
    urls = {i['url'] for i in items}
    answer = _ask(TECHNOLOG, {'items': items[:40], 'catalog': catalog()}, TECH_SCHEMA, force)
    tech = [t for t in answer.get('tech', []) if isinstance(t, dict) and t.get('source_url') in urls]
    if tech:
        tech = _drop(tech, _ask(TECHNOLOG_CHECK, {'items': items[:40], 'tech': tech}, CHECK_SCHEMA, force, True))
    data = {'summary': answer.get('summary', ''), 'tech': tech, 'authors': _authors()}
    body = chr(10).join([data['summary'], ''] + [f"- {t['tool']} [{t['license']}, wysiłek {t['effort']}, wartość {t['value']}/10]: "
                                                f"{t['use_here']} ({t['source_url']})" for t in tech]).strip()
    return _save('technolog', 'finding', f'Technologie do podłączenia: {timezone.localdate():%d.%m.%Y}', body, data, [t['source_url'] for t in tech])


# ---------- Wynalazca ----------
def inventory():
    """Spis źródeł z liczbami z bazy (Wynalazca wie, na czym może budować)."""
    from news.clinic_models import ClinicDailyMessage, ClinicInterview, SpinDiagnosis
    from news.models import Article, Ballot, ParliamentaryVoting
    from news.political_models import PoliticalPost, PublicFigure, PublicFigureOrganisationRelation
    from news.public_records_models import PublicRecord
    counts = {}
    for label, model, flt in (('artykuły', Article, {}), ('wpisy polityków', PoliticalPost, {}), ('diagnozy', SpinDiagnosis, {}),
                              ('przekazy dnia', ClinicDailyMessage, {}), ('wywiady', ClinicInterview, {}),
                              ('dokumenty Sejmu i urzędów', PublicRecord, {}), ('głosowania Sejmu', ParliamentaryVoting, {}),
                              ('głosy imienne', Ballot, {}), ('osoby publiczne', PublicFigure, {'archived': False}),
                              ('potwierdzone funkcje w KRS', PublicFigureOrganisationRelation, {'verification_status': 'confirmed'})):
        try:
            counts[label] = model.objects.filter(**flt).count()
        except Exception:  # noqa: BLE001 - spis nie może zatrzymać pomysłów
            counts[label] = None
    return {'sources': INVENTORY, 'counts': counts}


def wynalazca(force=False):
    from news import przeszlosc
    previous = [i.get('title') for n in AgentNote.objects.filter(agent='wynalazca', kind='finding')[:6]
                for i in (n.scores or {}).get('ideas', [])]
    plan = _last('architekt', 'report')
    data = {'inventory': inventory(), 'catalog': catalog(), 'previous': previous[:60],
            'plan': [i.get('title') for i in ((plan.scores or {}).get('items', []) if plan else [])],
            'topics': [t['topic'] for t in przeszlosc.auto_topics()][:6]}
    answer = _ask(WYNALAZCA, data, IDEAS_SCHEMA, force)
    ideas = [i for i in answer.get('ideas', []) if isinstance(i, dict) and i.get('title') and i.get('title') not in previous][:10]
    if ideas:
        ideas = _drop(ideas, _ask(WYNALAZCA_CHECK, {**data, 'ideas': ideas}, CHECK_SCHEMA, force, True))
    ideas.sort(key=lambda i: -int(i.get('wow') or 0))
    result = {'summary': answer.get('summary', ''), 'ideas': ideas, 'authors': _authors()}
    body = chr(10).join([result['summary'], ''] + [
        f"- {i['title']} [{i['tier']}, wow {i.get('wow')}/10]: {i['what']}{chr(10)}  Dlaczego nikt tego nie ma: {i['why_unique']}"
        f"{chr(10)}  Przykład: {i['example']}{chr(10)}  Dane: {', '.join(i.get('data_used', []))}" for i in ideas]).strip()
    return _save('wynalazca', 'finding', f'Nowe pomysły: {len(ideas)} ({timezone.localdate():%d.%m.%Y})', body, result)


# ---------- Architekt ----------
def architekt(force=False):
    def latest(agent, kind):
        note = _last(agent, kind)
        return {'note': note.pk, **(note.scores or {})} if note else {}
    inputs = {'catalog': catalog(), 'gaps': latest('kartograf', 'finding'), 'ideas': latest('wynalazca', 'finding'), 'tech': latest('technolog', 'finding'), 'sources': latest('zwiadowca', 'finding'),
              'legal': latest('prawnik', 'review'), 'tests': latest('dziennikarz', 'review'), 'data': latest('kontroler', 'audit'),
              'rules': LEGAL}
    for key in ('gaps', 'ideas', 'tech', 'sources', 'legal', 'tests'):
        inputs[key].pop('authors', None)
    answer = _ask(ARCHITEKT, inputs, PLAN_SCHEMA, force)
    items = [i for i in answer.get('items', []) if isinstance(i, dict)][:10]
    if items:
        items = _drop(items, _ask(ARCHITEKT_CHECK, {**inputs, 'plan': items}, CHECK_SCHEMA, force, True))
    data = {'summary': answer.get('summary', ''), 'items': items, 'authors': _authors()}
    lines = [data['summary'], '']
    for n, i in enumerate(items, 1):
        lines += [f"{n}. {i['title']} [{i['tier']}, wysiłek {i['effort']}, wartość {i['value']}/10]", f"   Dlaczego: {i['why']}",
                  '   Odbiór: ' + '; '.join(i.get('acceptance', [])), f"   Zlecenie: {i['brief']}"]
    report = _save('architekt', 'report', f'Plan rozwoju przeszłość.today: {timezone.localdate():%d.%m.%Y}', chr(10).join(lines).strip(),
                   data, notify=True)
    for i in items[:5]:  # pięć najważniejszych jako osobne pomysły do decyzji (i do krytyki Seby)
        AgentNote.objects.create(agent='architekt', kind='idea', status='new', title=f"przeszłość.today: {i['title']}"[:240],
                                 body=f"{i['why']}{chr(10)}Odbiór: {'; '.join(i.get('acceptance', []))}{chr(10)}Zlecenie: {i['brief']}",
                                 score=max(0, min(100, int(i.get('value') or 0) * 10)), scores={'plan': report.pk, **i})
    return report


ORDER = [('kontroler', kontroler), ('dziennikarz', dziennikarz), ('kartograf', kartograf), ('zwiadowca', zwiadowca), ('wynalazca', wynalazca), ('technolog', technolog),
         ('prawnik', prawnik), ('architekt', architekt)]


def due(agent):
    if agent == 'prawnik':  # gdy są nowe propozycje do oceny
        last = _last('prawnik', 'review')
        return AgentNote.objects.filter(agent__in=['kartograf', 'zwiadowca', 'wynalazca', 'technolog'], kind='finding',
                                        **({'created_at__gt': last.created_at} if last else {})).exists()
    last = AgentNote.objects.filter(agent=agent).exclude(kind='idea').first()
    return last is None or timezone.now() - last.created_at >= EVERY[agent]


def step(force=False, only=None):
    """Krok Pracowni: każda rola, której termin minął; jedna awaria nie zatrzymuje pozostałych."""
    done = {}
    for agent, run in ORDER:
        if (only and agent not in only) or (not force and not due(agent)):
            continue
        try:
            note = run(force)
            done[agent] = note.pk if note else None
        except common.WindowClosed as error:
            done[agent] = f'czeka: {error}'
        except Exception as error:  # noqa: BLE001 - raport dla panelu, kolejne role działają dalej
            done[agent] = f'błąd: {type(error).__name__}: {str(error)[:160]}'
    return done
