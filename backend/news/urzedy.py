"""Rejestr urzędów: kto dziś pełni najważniejsze funkcje w państwie, a kto pełnił je wcześniej.

Modele językowe mają stare wiadomości (np. „prezydent Andrzej Duda” po 6.08.2025). Ten rejestr jest jedynym źródłem
prawdy o urzędach dla promptów (blok „Aktualne urzędy na dzień …”) i dla Korektora (news/korektor.py).

Zasada: każdy wpis ma źródło. `pewne=False` (oznaczenie [DP]) - pozycja niepotwierdzona w dwóch niezależnych źródłach
albo w trakcie zmiany; taki wpis nie trafia do promptów ani do reguł Korektora.
Stan na 23.10.2026; weryfikacja 22.10.2026 wyszukiwarką (oficjalne strony gov.pl, sejm.gov.pl i senat.gov.pl nie
otwierały się z sesji w chmurze - koordynator potwierdza je przy wdrożeniu, zob. raport Korektora).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

STAN_NA = date(2026, 10, 23)

PREZYDENT_URL = 'https://www.prezydent.pl/prezydent'
RZAD_URL = 'https://www.gov.pl/web/premier/sklad-rady'
SEJM_URL = 'https://www.sejm.gov.pl/sejm10.nsf/page.xsp/prezydium_sejmu'
SENAT_URL = 'https://www.senat.gov.pl/o-senacie/organy/prezydium-senatu/'
KLUBY_URL = 'https://www.sejm.gov.pl/sejm10.nsf/kluby.xsp'
REKONSTRUKCJA_2025 = 'https://tvn24.pl/polska/rekonstrukcja-rzadu-pelna-lista-ministerstw-i-ministrow-st8567971'


@dataclass(frozen=True)
class Urzad:
    klucz: str                  # stały identyfikator urzędu, np. 'prezydent'
    urzad: str                  # nazwa do promptu
    osoba: str
    od: date | None             # data objęcia (None - niepewna, nie podajemy)
    zrodlo: str                 # oficjalna strona
    potwierdzenie: str = ''     # drugie, niezależne źródło (media), gdy oficjalna strona była niedostępna
    pewne: bool = True
    uwaga: str = ''
    # Rdzenie słów urzędu w tekście (z odmianą). Puste - urząd nie ma reguły „urząd + nazwisko”.
    slowa: tuple[str, ...] = ()
    jedyny: bool = True         # jedna osoba w urzędzie (prezydent, premier, minister danego resortu)


@dataclass(frozen=True)
class Byly:
    osoba: str
    klucz: str                  # urząd z Urzad.klucz
    urzad: str
    od: date | None
    do: date
    zrodlo: str


@dataclass(frozen=True)
class Osoba:
    """Formy nazwiska w odmianie - do wykrywania „urząd + nazwisko” w tekście."""
    nazwa: str
    formy: tuple[str, ...] = field(default=())


def _d(text: str) -> date:
    return date.fromisoformat(text)


RZAD_2023 = _d('2023-12-13')
RZAD_2025 = _d('2025-07-24')

PREZYDENT_SLOWA = ('prezydent', 'prezydenta', 'prezydentem', 'prezydentowi', 'prezydencie', 'głowa państwa', 'głowy państwa')
PREMIER_SLOWA = ('premier', 'premiera', 'premierem', 'premierowi', 'prezes rady ministrów', 'prezesa rady ministrów', 'szef rządu', 'szefa rządu')
MARSZALEK_SEJMU = ('marszałek sejmu', 'marszałka sejmu', 'marszałkiem sejmu', 'marszałkowi sejmu')
MARSZALEK_SENATU = ('marszałek senatu', 'marszałka senatu', 'marszałkiem senatu', 'marszałkowi senatu', 'marszałkini senatu')


def _minister(*rdzenie: str) -> tuple[str, ...]:
    return tuple(f'{forma} {rdzen}' for rdzen in rdzenie
                 for forma in ('minister', 'ministra', 'ministrem', 'ministrowi', 'ministrze', 'szef', 'szefa', 'szefem'))


URZEDY: tuple[Urzad, ...] = (
    Urzad('prezydent', 'Prezydent RP', 'Karol Nawrocki', _d('2025-08-06'), PREZYDENT_URL,
          'https://ipn.gov.pl/pl/aktualnosci/227708,Zaprzysiezenie-dr-Karola-Nawrockiego-na-Prezydenta-RP.pdf',
          slowa=PREZYDENT_SLOWA),
    Urzad('premier', 'Prezes Rady Ministrów (premier)', 'Donald Tusk', RZAD_2023, 'https://www.gov.pl/web/premier',
          REKONSTRUKCJA_2025, slowa=PREMIER_SLOWA),
    Urzad('marszalek-sejmu', 'Marszałek Sejmu', 'Włodzimierz Czarzasty', _d('2025-11-18'), SEJM_URL,
          'https://www.rp.pl/polityka/art43207461-wlodzimierz-czarzasty-nie-moze-byc-pewien-ze-zostanie-marszalkiem-watpliwosci-w-koalicji',
          slowa=MARSZALEK_SEJMU),
    Urzad('marszalek-senatu', 'Marszałek Senatu', 'Małgorzata Kidawa-Błońska', _d('2023-11-13'), SENAT_URL,
          'https://www.senat.gov.pl/aktualnoscilista/art,15888,malgorzata-kidawa-blonska-marszalkiem-senatu-rp-xi-kadencji.html',
          uwaga='rotacji w Senacie nie było', slowa=MARSZALEK_SENATU),
    # Rada Ministrów po rekonstrukcji z 24.07.2025 (zgodne zestawienia TVN24, Forsal, Rynek Zdrowia; KPRM: skład Rady).
    Urzad('wicepremier-msz', 'Wicepremier, minister spraw zagranicznych', 'Radosław Sikorski', None, RZAD_URL,
          REKONSTRUKCJA_2025, slowa=_minister('spraw zagranicznych', 'msz', 'dyplomacji')),
    Urzad('wicepremier-mon', 'Wicepremier, minister obrony narodowej', 'Władysław Kosiniak-Kamysz', RZAD_2023, RZAD_URL,
          REKONSTRUKCJA_2025, slowa=_minister('obrony narodowej', 'obrony', 'mon')),
    Urzad('wicepremier-cyfryzacja', 'Wicepremier, minister cyfryzacji', 'Krzysztof Gawkowski', RZAD_2023, RZAD_URL,
          REKONSTRUKCJA_2025, slowa=_minister('cyfryzacji')),
    Urzad('finanse', 'Minister finansów i gospodarki', 'Andrzej Domański', None, RZAD_URL, REKONSTRUKCJA_2025,
          uwaga='20.10.2026 Sejm odrzucił wotum nieufności; wniosek premiera o powołanie na wicepremiera czeka na decyzję '
                'prezydenta [DP]', slowa=_minister('finansów', 'mf')),
    Urzad('mswia', 'Minister spraw wewnętrznych i administracji', 'Marcin Kierwiński', RZAD_2025, RZAD_URL,
          REKONSTRUKCJA_2025, slowa=_minister('spraw wewnętrznych', 'mswia')),
    Urzad('sprawiedliwosc', 'Minister sprawiedliwości, prokurator generalny', 'Waldemar Żurek', RZAD_2025, RZAD_URL,
          REKONSTRUKCJA_2025, slowa=_minister('sprawiedliwości') + ('prokurator generalny', 'prokuratora generalnego')),
    Urzad('energia', 'Minister energii', 'Miłosz Motyka', RZAD_2025, RZAD_URL, REKONSTRUKCJA_2025, slowa=_minister('energii')),
    Urzad('edukacja', 'Minister edukacji', 'Barbara Nowacka', RZAD_2023, RZAD_URL, REKONSTRUKCJA_2025,
          slowa=_minister('edukacji', 'edukacji narodowej')),
    Urzad('klimat', 'Minister klimatu i środowiska', 'Paulina Hennig-Kloska', RZAD_2023, RZAD_URL, REKONSTRUKCJA_2025,
          slowa=_minister('klimatu', 'środowiska')),
    Urzad('infrastruktura', 'Minister infrastruktury', 'Dariusz Klimczak', RZAD_2023, RZAD_URL, REKONSTRUKCJA_2025,
          slowa=_minister('infrastruktury')),
    Urzad('rolnictwo', 'Minister rolnictwa i rozwoju wsi', 'Stefan Krajewski', RZAD_2025, RZAD_URL, REKONSTRUKCJA_2025,
          slowa=_minister('rolnictwa')),
    Urzad('zdrowie', 'Minister zdrowia', 'Jolanta Sobierańska-Grenda', RZAD_2025, RZAD_URL,
          'https://forsal.pl/kraj/aktualnosci/artykuly/9846752,rekonstrukcja-rzadu-znamy-nazwiska-nowych-ministrow-lista.html',
          slowa=_minister('zdrowia')),
    Urzad('kultura', 'Minister kultury i dziedzictwa narodowego', 'Marta Cienkowska', RZAD_2025, RZAD_URL,
          REKONSTRUKCJA_2025, slowa=_minister('kultury')),
    Urzad('sport', 'Minister sportu i turystyki', 'Jakub Rutnicki', RZAD_2025, RZAD_URL, REKONSTRUKCJA_2025,
          slowa=_minister('sportu')),
    Urzad('nauka', 'Minister nauki i szkolnictwa wyższego', 'Marcin Kulasek', None, RZAD_URL, REKONSTRUKCJA_2025,
          slowa=_minister('nauki')),
    Urzad('fundusze', 'Minister funduszy i polityki regionalnej', 'Katarzyna Pełczyńska-Nałęcz', RZAD_2023, RZAD_URL,
          REKONSTRUKCJA_2025, slowa=_minister('funduszy')),
    Urzad('rodzina', 'Minister rodziny, pracy i polityki społecznej', 'Agnieszka Dziemianowicz-Bąk', RZAD_2023, RZAD_URL,
          REKONSTRUKCJA_2025, slowa=_minister('rodziny', 'pracy')),
    Urzad('aktywa', 'Minister aktywów państwowych', 'Wojciech Balczun', RZAD_2025, RZAD_URL, REKONSTRUKCJA_2025,
          slowa=_minister('aktywów państwowych', 'aktywów')),
    Urzad('koordynator-sluzb', 'Minister-członek RM, koordynator służb specjalnych', 'Tomasz Siemoniak', RZAD_2025, RZAD_URL,
          REKONSTRUKCJA_2025, slowa=('koordynator służb specjalnych', 'koordynatora służb specjalnych', 'koordynatorem służb specjalnych')),
    Urzad('kprm', 'Szef Kancelarii Prezesa Rady Ministrów', 'Jan Grabiec', None, 'https://www.gov.pl/web/premier', '',
          slowa=('szef kprm', 'szefa kprm', 'szefem kprm', 'szef kancelarii premiera', 'szefa kancelarii premiera')),
    Urzad('kprp', 'Szef Kancelarii Prezydenta RP', 'Zbigniew Bogucki', None, PREZYDENT_URL,
          'https://www.polsatnews.pl/gosc-wydarzen/2026-10-20/bogucki-o-awansie-domanskiego-tusk-idzie-po-prostu-na-sciane/',
          slowa=('szef kancelarii prezydenta', 'szefa kancelarii prezydenta', 'szefem kancelarii prezydenta')),
    Urzad('rzecznik-prezydenta', 'Rzecznik prasowy Prezydenta RP', 'Rafał Leśkiewicz', None, PREZYDENT_URL,
          'https://www.tvp.info/96052203/prof-antoni-dudek-w-pytaniu-dnia-21102026-czy-prezydent-nawrocki-zablokuje-nominacje-andrzej-domanskiego',
          slowa=('rzecznik prezydenta', 'rzecznika prezydenta', 'rzecznikiem prezydenta')),
    # Partie: przewodniczący.
    Urzad('prezes-pis', 'Prezes PiS', 'Jarosław Kaczyński', None, 'https://pis.org.pl/partia/wladze-partii',
          slowa=('prezes pis', 'prezesa pis', 'prezesem pis', 'prezes prawa i sprawiedliwości', 'prezesa prawa i sprawiedliwości')),
    Urzad('lider-ko', 'Przewodniczący Koalicji Obywatelskiej', 'Donald Tusk', None, 'https://ko.org.pl/', '',
          slowa=('przewodniczący ko', 'przewodniczącego ko', 'przewodniczący platformy', 'przewodniczącego platformy', 'lider ko')),
    Urzad('prezes-psl', 'Prezes PSL', 'Władysław Kosiniak-Kamysz', None, 'https://psl.pl/', '',
          slowa=('prezes psl', 'prezesa psl', 'prezesem psl', 'prezes ludowców', 'prezesa ludowców')),
    Urzad('lider-nowa-lewica', 'Przewodniczący Nowej Lewicy', 'Włodzimierz Czarzasty', _d('2025-12-14'), 'https://lewica.org.pl/',
          'https://pl.wikipedia.org/wiki/Nowa_Lewica', slowa=('przewodniczący nowej lewicy', 'przewodniczącego nowej lewicy',
                                                             'szef nowej lewicy', 'szefa nowej lewicy', 'lider nowej lewicy')),
    Urzad('lider-razem', 'Współprzewodniczący partii Razem', 'Adrian Zandberg, Aleksandra Owca', _d('2024-12-03'),
          'https://partiarazem.pl/', 'https://pl.wikipedia.org/wiki/Lewica_Razem_(partia)', jedyny=False),
    Urzad('lider-polska-2050', 'Przewodniczący Polski 2050', 'Katarzyna Pełczyńska-Nałęcz', _d('2026-01-31'),
          'https://polska2050.pl/', 'https://www.polsatnews.pl/wiadomosc/2026-09-17/roszada-w-polsce-2050-szymon-holownia-z-nowa-funkcja/',
          pewne=False, uwaga='[DP] 22.10.2026 ogłosiła przekazanie przewodnictwa Szymonowi Hołowni - czekamy na potwierdzenie'),
    Urzad('lider-nowa-nadzieja', 'Prezes Nowej Nadziei (Konfederacja)', 'Sławomir Mentzen', None, 'https://konfederacja.pl/',
          pewne=False, uwaga='[DP] nie potwierdzone w tej sesji'),
    Urzad('lider-ruch-narodowy', 'Prezes Ruchu Narodowego (Konfederacja)', 'Krzysztof Bosak', None, 'https://konfederacja.pl/',
          pewne=False, uwaga='[DP] nie potwierdzone w tej sesji'),
    Urzad('lider-kkp', 'Prezes Konfederacji Korony Polskiej', 'Grzegorz Braun', None, 'https://koronapolska.pl/',
          pewne=False, uwaga='[DP] nie potwierdzone w tej sesji'),
    # Kluby poselskie: tabela Sejmu X kadencji (stan sierpień 2026, jedno źródło pośrednie) - [DP] do potwierdzenia na kluby.sejm.
    Urzad('klub-polska-2050', 'Przewodniczący klubu Polska 2050', 'Szymon Hołownia', _d('2026-09-17'), KLUBY_URL,
          'https://www.polsatnews.pl/wiadomosc/2026-09-17/roszada-w-polsce-2050-szymon-holownia-z-nowa-funkcja/'),
    Urzad('klub-ko', 'Przewodniczący klubu KO', 'Zbigniew Konwiński', None, KLUBY_URL, pewne=False, uwaga='[DP]'),
    Urzad('klub-pis', 'Przewodniczący klubu PiS', 'Mariusz Błaszczak', None, KLUBY_URL, pewne=False, uwaga='[DP]'),
    Urzad('klub-lewica', 'Przewodnicząca klubu Lewicy', 'Anna Maria Żukowska', None, KLUBY_URL, pewne=False, uwaga='[DP]'),
    Urzad('klub-psl', 'Przewodniczący klubu PSL', 'Krzysztof Paszyk', None, KLUBY_URL, pewne=False, uwaga='[DP]'),
    Urzad('klub-konfederacja', 'Przewodniczący klubu Konfederacji', 'Grzegorz Płaczek', None, KLUBY_URL, pewne=False, uwaga='[DP]'),
    Urzad('klub-rozwoj-plus', 'Przewodniczący klubu Rozwój Plus', 'Łukasz Schreiber', None, KLUBY_URL, pewne=False,
          uwaga='[DP] klub z rozłamu w PiS (lipiec 2026)'),
)

BYLI: tuple[Byly, ...] = (
    Byly('Andrzej Duda', 'prezydent', 'Prezydent RP', _d('2015-08-06'), _d('2025-08-06'), PREZYDENT_URL),
    Byly('Bronisław Komorowski', 'prezydent', 'Prezydent RP', _d('2010-08-06'), _d('2015-08-06'), PREZYDENT_URL),
    Byly('Mateusz Morawiecki', 'premier', 'Prezes Rady Ministrów', _d('2017-12-11'), RZAD_2023, 'https://www.gov.pl/web/premier'),
    Byly('Beata Szydło', 'premier', 'Prezes Rady Ministrów', _d('2015-11-16'), _d('2017-12-11'), 'https://www.gov.pl/web/premier'),
    Byly('Szymon Hołownia', 'marszalek-sejmu', 'Marszałek Sejmu', _d('2023-11-13'), _d('2025-11-18'), SEJM_URL),
    Byly('Elżbieta Witek', 'marszalek-sejmu', 'Marszałek Sejmu', _d('2019-08-09'), _d('2023-11-13'), SEJM_URL),
    Byly('Adam Bodnar', 'sprawiedliwosc', 'Minister sprawiedliwości', RZAD_2023, RZAD_2025, REKONSTRUKCJA_2025),
    Byly('Zbigniew Ziobro', 'sprawiedliwosc', 'Minister sprawiedliwości', _d('2015-11-16'), RZAD_2023, RZAD_URL),
    Byly('Izabela Leszczyna', 'zdrowie', 'Minister zdrowia', RZAD_2023, RZAD_2025, REKONSTRUKCJA_2025),
    Byly('Czesław Siekierski', 'rolnictwo', 'Minister rolnictwa', RZAD_2023, RZAD_2025, REKONSTRUKCJA_2025),
    Byly('Hanna Wróblewska', 'kultura', 'Minister kultury', None, RZAD_2025, REKONSTRUKCJA_2025),
    Byly('Sławomir Nitras', 'sport', 'Minister sportu', RZAD_2023, RZAD_2025, REKONSTRUKCJA_2025),
    Byly('Mariusz Błaszczak', 'wicepremier-mon', 'Minister obrony narodowej', _d('2018-01-09'), RZAD_2023, RZAD_URL),
)

# Odmiana nazwisk (mianownik, dopełniacz, celownik, biernik, narzędnik, miejscownik) - tylko dla osób w regułach.
ODMIANA: dict[str, tuple[str, ...]] = {
    'Andrzej Duda': ('duda', 'dudy', 'dudzie', 'dudę', 'dudą'),
    'Bronisław Komorowski': ('komorowski', 'komorowskiego', 'komorowskiemu', 'komorowskim'),
    'Karol Nawrocki': ('nawrocki', 'nawrockiego', 'nawrockiemu', 'nawrockim'),
    'Mateusz Morawiecki': ('morawiecki', 'morawieckiego', 'morawieckiemu', 'morawieckim'),
    'Beata Szydło': ('szydło',),
    'Donald Tusk': ('tusk', 'tuska', 'tuskowi', 'tuskiem'),
    'Szymon Hołownia': ('hołownia', 'hołowni', 'hołownię', 'hołownią'),
    'Elżbieta Witek': ('witek',),
    'Włodzimierz Czarzasty': ('czarzasty', 'czarzastego', 'czarzastemu', 'czarzastym'),
    'Małgorzata Kidawa-Błońska': ('kidawa-błońska', 'kidawy-błońskiej', 'kidawą-błońską', 'kidawę-błońską', 'kidawa', 'kidawy'),
    'Adam Bodnar': ('bodnar', 'bodnara', 'bodnarowi', 'bodnarem'),
    'Zbigniew Ziobro': ('ziobro', 'ziobry', 'ziobrze', 'ziobrę', 'ziobrą'),
    'Waldemar Żurek': ('żurek', 'żurka', 'żurkowi', 'żurkiem'),
    'Izabela Leszczyna': ('leszczyna', 'leszczyny', 'leszczynie', 'leszczynę', 'leszczyną'),
    'Jolanta Sobierańska-Grenda': ('sobierańska-grenda', 'sobierańskiej-grendy', 'sobierańską-grendą', 'sobierańską-grendę'),
    'Czesław Siekierski': ('siekierski', 'siekierskiego', 'siekierskiemu', 'siekierskim'),
    'Stefan Krajewski': ('krajewski', 'krajewskiego', 'krajewskiemu', 'krajewskim'),
    'Hanna Wróblewska': ('wróblewska', 'wróblewskiej', 'wróblewską'),
    'Marta Cienkowska': ('cienkowska', 'cienkowskiej', 'cienkowską'),
    'Sławomir Nitras': ('nitras', 'nitrasa', 'nitrasowi', 'nitrasem'),
    'Jakub Rutnicki': ('rutnicki', 'rutnickiego', 'rutnickiemu', 'rutnickim'),
    'Mariusz Błaszczak': ('błaszczak', 'błaszczaka', 'błaszczakowi', 'błaszczakiem'),
    'Władysław Kosiniak-Kamysz': ('kosiniak-kamysz', 'kosiniaka-kamysza', 'kosiniakowi-kamyszowi', 'kosiniakiem-kamyszem'),
}


def pewne() -> list[Urzad]:
    return [row for row in URZEDY if row.pewne]


def urzad(klucz: str) -> Urzad | None:
    return next((row for row in URZEDY if row.klucz == klucz and row.pewne), None)


def byli(klucz: str) -> list[Byly]:
    return [row for row in BYLI if row.klucz == klucz]


def _data(day: date) -> str:
    return day.strftime('%d.%m.%Y')


def blok(day: date | None = None) -> str:
    """Krótki blok do promptu: aktualni urzędnicy i najważniejsi byli. Tylko pozycje pewne."""
    from django.utils import timezone
    day = day or timezone.localdate()
    lines = [f'Aktualne urzędy na dzień {_data(day)} (rejestr spin.clinic, ma pierwszeństwo przed Twoją wiedzą):']
    lines += [f'- {row.urzad}: {row.osoba}' + (f' (od {_data(row.od)})' if row.od else '') for row in pewne()]
    lines.append('Byli (nie pełnią już tych funkcji): ' + '; '.join(
        f'{row.osoba} - {row.urzad} ' + (f'{row.od.year}-{row.do.year}' if row.od else f'do {row.do.year}')
        for row in BYLI))
    lines.append('Pisząc o osobie, używaj obecnej funkcji z rejestru; o byłych pisz „były/była”. Nie zgaduj funkcji spoza rejestru.')
    return '\n'.join(lines)


def obecna_funkcja(osoba: str) -> list[str]:
    key = osoba.casefold().strip()
    return [row.urzad for row in pewne() if key in [name.strip().casefold() for name in row.osoba.split(',')]]


def formy(osoba: str) -> tuple[str, ...]:
    if osoba in ODMIANA:
        return ODMIANA[osoba]
    return (osoba.split()[-1].casefold(),)


BYLY_PRZED = re.compile(r'(?:był\w*|b\.|ówczesn\w*|poprzedni\w*|dawn\w*|eks-?|ex-?|wcześniejsz\w*|świętej pamięci)\s*$', re.I)
