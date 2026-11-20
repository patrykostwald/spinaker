import json
import re
import unicodedata
from datetime import datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from django.utils import timezone

from ..models import Wpis, Zdarzenie
from ..zbieranie import Adapter, BladFormatu
from .wspolne import DrzewoHTML, LIMIT_TRESCI, WARSZAWA, data_iso, odczytaj, uprosc, wpis

LISTA = "https://www.gov.pl/web/rcb/komunikaty"
KARTA = re.compile(r"/web/rcb/[a-z0-9][a-z0-9-]*")
GODZINA = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
AKTUALIZACJA = re.compile(r"^aktualizacja\b", re.I)
ODWOLANIE = re.compile(
    r"\b(?:odwołan[oi]|anulowano)\s+(?:alert|ostrzeżenie)\b|"
    r"\b(?:alert|ostrzeżenie)\s+(?:został\w*\s+)?(?:odwołan[ey]|anulowan[ey])\b|"
    r"\b(?:odwołanie|koniec)\s+(?:alertu|zagrożenia)\b|"
    r"\bzakończył się atak [^.]{1,100}\.\s+brak zagrożenia na terenie Polski\b",
    re.I,
)
WOJEWODZTWA = {
    "dolnośląsk": "02", "kujawsko-pomorsk": "04", "lubelsk": "06", "lubusk": "08",
    "łódzk": "10", "małopolsk": "12", "mazowieck": "14", "opolsk": "16",
    "podkarpack": "18", "podlask": "20", "pomorsk": "22", "śląsk": "24",
    "świętokrzysk": "26", "warmińsko-mazursk": "28", "wielkopolsk": "30", "zachodniopomorsk": "32",
}
WOJ_NOMINATYW = {kod: nazwa + "ie" for nazwa, kod in WOJEWODZTWA.items()}
WOJ_RDZEN = {kod: nazwa for nazwa, kod in WOJEWODZTWA.items()}
_RDZENIE_WOJ = "|".join(WOJEWODZTWA)
NAZWA_WOJ = re.compile(r"(?<![\w-])(" + _RDZENIE_WOJ + r")(?:ie(?:go|m)?|ich)\b", re.I)
# „w woj. lubelskim”: miejscownik (-im/-ym/-ej) tylko po „woj.”, „województwie” lub „województwach”, bo „w powiecie lubelskim”
# to powiat, nie województwo. Po pierwszej nazwie mogą iść kolejne: „w woj. lubelskim i podkarpackim”, „…, małopolskim oraz
# w woj. śląskim” (recenzja PR #38, R38d P1-2).
_NAZWA_MIEJSCOWNIK = r"(?<![\w-])(?:" + _RDZENIE_WOJ + r")(?:im|ym|ej)\b"
WOJ_MIEJSCOWNIK = re.compile(
    r"\b(?:woj\.|województwie|województwach)\s+" + _NAZWA_MIEJSCOWNIK
    + r"(?:(?:\s*,\s*|\s+(?:i|oraz)\s+)(?:(?:woj\.|województwie)\s+)?" + _NAZWA_MIEJSCOWNIK + r")*", re.I,
)
NAZWA_MIEJSCOWNIK = re.compile(r"(?<![\w-])(" + _RDZENIE_WOJ + r")(?:im|ym|ej)\b", re.I)
TEKST_MIEJSCA = re.compile(r"^alert rcb .*?(?:odbiorc|teren|województw|powiat)|^[-•]\s", re.I)
NAGLOWEK_ALERTU = re.compile(r"^\W*alert rcb\b", re.I)
# Nagłówek listy jednostek: z dwukropkiem („powiaty: A, B”) albo bez („w powiatach A i B”, „powiat świdnicki”, „w mieście Kraków”).
NAGLOWEK_JEDNOSTEK = re.compile(
    r"(?:\b(?:w|we)\s+)?\b(?P<typ>powiat|powiec|gmin|miast|mieśc|pow\.)[^\W\d_]*(?:\s*:\s*|\s+(?=[^\W\d_]))", re.I,
)
NAGLOWEK_WOJEWODZTW = re.compile(r"\bwojewództw(?:o|a)?\s*:", re.I)
TYPY_JEDNOSTEK = {"powiat": "", "powiec": "", "pow.": "", "gmin": "gmina ", "miast": "miasto ", "mieśc": "miasto "}
# Kropka po skrócie („godz.”, „ul.”, „woj.”, „pow.”, „al.”) nie kończy zdania (Z6P7 pkt 7).
KONIEC_ZDANIA = re.compile(r"(?<!\bwoj)(?<!\bgodz)(?<!\bul)(?<!\bpow)(?<!\bal)\.(?:\s|$)", re.I)
KONCOWKA_SEGMENTU = re.compile(
    r"[\s,;:\-\u2013\u2014]*(?:\b(?:oraz|i|a|także|w|we|woj|województwie|województwa|województwo)\b\.?[\s,;:\-\u2013\u2014]*)*$", re.I,
)
PODZIAL_ELEMENTOW = re.compile(r"[,;]|\s+(?:i|oraz)\s+", re.I)
# „nr” samo (bez „ul.”, „al.”) nie jest rozpoznanym adresem: element z „nr” to element nieczytelny (Z6P7a pkt 5), nie ciche pominięcie.
ADRES_SLOWO = re.compile(r"\b(?:ul(?:ica|icy|icę)?|al(?:eja|ei|eję)?|plac|os(?:iedle)?)\b", re.I)
ADRES = re.compile(r"\d|\bnr\b|" + ADRES_SLOWO.pattern, re.I)
# Nazwa jednostki: najwyżej 3 wyrazy (Nowy Dwór Mazowiecki); powiat musi być też w słowniku, miasto i gmina: z wielkiej litery.
NAZWA_JEDNOSTKI = re.compile(r"[^\W\d_]+(?:[ -][^\W\d_]+){0,2}")
ODSTEP_KARTY = timedelta(minutes=10)
CZESC_REGIONU = re.compile(r"\bczęś(?:ć|ci)\s+(?:woj\.|województw)", re.I)
WZMIANKA_JEDNOSTKI = re.compile(r"\b(?:powiat|powiec|gmin|miast|mieśc)[^\W\d_]*|\bpow\.", re.I)
ROZDZIELNIK = r"[\s,;:\-\u2013\u2014]"
# Zdanie z zaleceniem, nie z odbiorcami: czasownik zalecenia w dowolnym miejscu zdania („Omijaj miasto Chełm”, „W powiecie
# chełmskim zalecamy pozostanie w domach”, „Dla mieszkańców … zalecamy …”). Formy dwuznaczne („bądź”, „ogranicz”) tylko w
# znaczeniu zalecenia, żeby „bądź” (albo) i „ograniczony” nie wyłączały zdania o odbiorcach (R38d P1-3).
REKOMENDACJA = re.compile(
    r"^\W*nie\b|"
    r"\b(?:zalecam\w*|zalecan\w*|zaleca\w*|zalecen\w*|prosimy|prosz\w+|radzimy|apelujemy|rekomendujemy|należy|trzeba|warto|"
    r"powinn\w+|powinien|powinno|omijaj\w*|omijać|unikaj\w*|unikać|zachowaj\w*|zachować|stosuj\w*|stosować|"
    r"pozostań\w*|pozostać|pozostanie|zostań\w*|ogranicz|ograniczaj\w*|zabezpiecz\w*|sprawdź\w*|sprawdzaj\w*|"
    r"ewakuuj\w*|ewakuować|schro(?:ń|ńcie|nić)|zamknij\w*|zamykaj\w*|opuść\w*|opuszczaj\w*|pamiętaj\w*|przygotuj\w*|"
    r"wychodź\w*|wychodzić|oddal(?:aj\w*|ić)|udaj(?:cie)?\s+się|udać\s+się|bądź(?:cie)?\s+(?:ostrożn|czujn|gotow)\w*)\b", re.I,
)
# Wyłączenie jednostek: po tych słowach jednostki nie są objęte alertem („z wyłączeniem powiatu białostockiego”). „Bez” tylko
# przed nazwą typu jednostki, żeby „bez względu na…” nie ucinało zdania (R38d P1-1).
WYLACZENIE = re.compile(
    r"\b(?:(?:z|za)\s+wyłączeniem|(?:z|za)\s+wyjątkiem|wyłączając|poza|oprócz|nie\s+(?:dotyczy|obejmuje|obowiązuje)(?:\s+już)?)\b|"
    r"\bbez\s+(?=(?:woj\.|województw|powiat|powiec|gmin|miast|mieśc))", re.I,
)
PREFIKS_WYLACZONE = "wyłączone: "
LINIA_WYLACZENIE_OGOLNE = PREFIKS_WYLACZONE + "nieokreślone"
LINIA_NIEUSTALONE = "nieustalone: nazwy jednostek"
PREFIKS_NIEUSTALONE = "nieustalone:"
PREFIKS_ZAKRES = "zakres:"
PREFIKSY_ZNACZNIKOW = (PREFIKS_WYLACZONE, PREFIKS_NIEUSTALONE, PREFIKS_ZAKRES)
# Zakres per województwo (R38d, zlecenie Z6P6): „zakres: lubelskie: cale|czesc|lista”. `lista`: źródło wymienia jednostki tego
# województwa (linie „lubelskie: chełmski”), `czesc`: część województwa bez wskazania jednostek („w części woj.”, „na południu woj.”),
# `cale`: całe województwo. Zakresy z kilku zdań tego samego województwa, które się różnią, scalamy do `czesc`.
# `lista` to lista ZAMKNIĘTA (Z6P7a): tylko gdy zdanie ma ściśle rozpoznany kształt (patrz `_zdanie_scisle`) i wszystkie jednostki tego
# województwa to powiaty ziemskie ze słownika. Każda inna lista jednostek („część woj., w tym powiat X”, „wybranych rejonów”,
# gmina, miasto, nazwa spoza słownika, zdanie z nieznanymi słowami) to `lista_otwarta`: front nie może wtedy powiedzieć „nie ma na liście”.
ZAKRES_LINIA = re.compile(r"zakres: ([^:]+): (cale|czesc|lista|lista_otwarta)")
RODZAJ_ZAKRESU = {"cale": 0, "czesc": 1, "lista": 2, "lista_otwarta": 3}
NAWIAS_WOJEWODZTWA = re.compile(r"\s*\(\s*(?:w\s+)?(?:woj\.|województwie|województwo)\s+([^()]+?)\s*\)", re.I)
NAWIAS_JEDNOSTKI = re.compile(r"\(\s*((?:powiat|powiec|gmin|miast|mieśc)[^()]*)\)", re.I)
# Zdanie o odbiorcach (R38d, Z6P6): nagłówek alertu („Alert RCB …”) albo czasownik wysłania, obowiązywania lub obejmowania
# („wysłany do odbiorców”, „obowiązuje”, „obejmuje”, „dotyczy”, „ogranicza się do”). Sama wzmianka o mieście lub województwie
# („Punkty pomocy otwarto w mieście Chełm”) nie zmienia zasięgu.
CZASOWNIK_ODBIORCOW = re.compile(
    r"\b(?:obowiązuj\w*|obejmuj\w*|obejm\w+|dotyczy|dotyczą|dotyczył\w*|"
    r"ogranicza\s+się|ograniczon\w+\s+do|zawężon\w+|zawężono)\b", re.I,
)
# Czasownik wysłania liczy się jako zdanie o odbiorcach tylko z podmiotem alertu: „Alert wysłano do mieszkańców…” tak,
# „Dodatkowych strażaków wysłano do miasta Radom w woj. mazowieckim” nie (Z6P7 pkt 3). Podmiot w mianowniku albo bierniku:
# „po alercie”, „w związku z alertem” go nie tworzą.
CZASOWNIK_WYSLANIA = re.compile(r"\b(?:wysł\w+|wysyła\w*|rozesł\w+|skierowan\w+)\b", re.I)
PODMIOT_ALERTU = re.compile(r"\b(?:alert|alerty|komunikat|komunikaty|ostrzeżenie|sms|wiadomość|powiadomienie)\b", re.I)
# „Nie obowiązuje już w powiecie puckim” bez podmiotu: wyłączenie, nie zalecenie „nie …” (Z6P7 pkt 4).
WYLACZENIE_BEZ_PODMIOTU = re.compile(r"^\W*nie\s+(?:dotyczy|obejmuje|obowiązuje)\b", re.I)
# Zdanie o zasięgu, którego nie rozpoznaliśmy w pełni (bez czasownika i nagłówka odbiorców), ale z jednostką lub województwem i
# słowem, które mogło zmienić znaczenie wcześniejszego zasięgu: nie zmieniamy zasięgu, tylko oznaczamy go jako nieustalony.
ZAWEZENIE = re.compile(r"\b(?:już\s+tylko|tylko|jedynie|wyłącznie|ogranicz\w+|zawęż\w+)\b", re.I)
PUNKT_LISTY = re.compile(r"^[-•]\s")
# Strukturalna linia listy odbiorców („- lubelskie - powiaty: A, B”, „gminy: A, B”): zaczyna się od typu jednostek z dwukropkiem,
# opcjonalnie po punkcie i nazwie województwa. Proza z dwukropkiem („Punkty pomocy w miastach: …”) nią nie jest.
STRUKTURA_LISTY = re.compile(
    r"^(?:[-•]\s*)?(?:(?:woj\.\s*)?[^\W\d_]+(?:-[^\W\d_]+)?\s*[-:\u2013\u2014]\s*)?(?:powiat|powiec|gmin|miast|mieśc)[^\W\d_]*\s*:", re.I,
)
CZESC_BEZ_NAZWY = re.compile(r"\bczęś(?:ć|ci)\s+(?:woj\.|województw\w*)\s*:\s*$", re.I)
# Odsyłacze przy nazwach: „włodawskim (1)”, „włodawskim [2]”, „włodawskim*”, „włodawskim¹”.
# Także „(odsyłacz nr 1)”, „(zob. nr 2)”, „nr 1” (Z6P7a pkt 5).
_NUMER_ODSYLACZA = r"(?:(?:odsyłacz|zob\.?|zobacz|przypis)\s*)*(?:nr\s*)?\d{1,2}"
ODSYLACZ = re.compile(
    r"\s*(?:\(\s*" + _NUMER_ODSYLACZA + r"\s*\)|\[\s*" + _NUMER_ODSYLACZA + r"\s*\]|\bnr\s*\d{1,2}\b|\*+|[¹²³⁰⁴-⁹]+)", re.I,
)
# Koniec wyłączenia w zdaniu: nowa grupa po spójniku („…z wyjątkiem powiatu puckiego, a także w woj. zachodniopomorskim”)
# albo nowe zdanie orzekające po średniku („…nie obowiązuje już w woj. X; obowiązuje w woj. Y”).
KONIEC_WYLACZENIA = re.compile(
    r"(?:,\s*|\s+)(?:a\s+także|także|oraz|i|a)\s+(?=(?:w|we)\s+(?:woj\.|województw)|woj\.)|"
    r";\s*(?=(?:alert\s+|komunikat\s+)?(?:obowiązuj|obejmuj|dotyczy)\w*)|"
    # „Oprócz powiatu X alert obejmuje również powiat Y”: orzeczenie twierdzące kończy wyłączenie, Y jest objęty (Z6P7 pkt 4);
    # „nie obejmuje” i „alert nie dotyczy” go nie kończą
    r"(?<!\bnie)(?:,\s*|\s+)(?:(?:alert|komunikat|ostrzeżeni)\w*(?:\s+rcb)?\s+)?(?:obejmuj|obowiązuj|dotycz)\w*\b", re.I,
)
# Zmiana zasięgu w aktualizacji: nowa lista zastępuje dotychczasową („Od 11:00 alert obejmuje wyłącznie powiat chełmski”,
# „obejmuje już tylko”).
ZMIANA_ZASIEGU = re.compile(
    r"\b(?:już\s+tylko|tylko|jedynie|wyłącznie|ogranicza\s+się\s+do|ograniczon\w+\s+do|zawężon\w+\s+do|zawężono\s+do)\b", re.I,
)
# Nagłówek aktualizacji: „Aktualizacja 11:00”, „Aktualizacja - g. 10:55”, „Aktualizacja! - 22:41”; treść po nim to początek aktualizacji.
NAGLOWEK_AKTUALIZACJI = re.compile(
    r"^aktualizacja\b[\s!:.\-\u2013\u2014]*(?:\(?\s*(?:z\s+|o\s+)?(?:godz(?:inie)?\.?|g\.?)?\s*(?:[01]?\d|2[0-3]):[0-5]\d\s*\)?)?"
    r"[\s!:.\-\u2013\u2014]*", re.I,
)
# Część województwa przed jego nazwą: „w części woj. X”, „na południu woj. X”, „w północno-wschodniej części woj. X”.
_KIERUNEK = r"(?:północn\w*|południow\w*|wschodni\w*|zachodni\w*|centraln\w*)"
CZESC_PRZED_NAZWA = re.compile(
    r"(?:\bczęś(?:ć|ci)|\b(?:wybran|niektór|poszczególn|określon)\w+\s+(?:rejon|obszar|teren|miejscowoś|region|okolic|czę|gmin|powiat|miast)\w*"
    r"|\bna\s+(?:północy|południu|wschodzie|zachodzie|północnym|południowym|wschodnim|zachodnim|centrum)(?:[\s-]+\w+)?"
    r"|\bw\s+" + _KIERUNEK + r"(?:[\s-]+" + _KIERUNEK + r")?\s+części)\s+(?:woj\.|województw\w*)\s*$", re.I,
)
LACZNIK_WOJEWODZTW = re.compile(r"\s*,\s*(?:(?:i|oraz)\s+)?|\s+(?:i|oraz)\s+", re.I)
# „powiecie A w woj. X”: „w woj.” zaraz po nazwie jednostki, nie po spójniku ani znaku rozdzielającym listę.
PO_JEDNOSTCE = re.compile(
    r"(?<![,;:\-\u2013\u2014\s])(?<!\boraz)(?<!\bi)(?<!\ba)(?<!\btakże)\s+(?:w|we)\s+(?:woj\.|województwie)\s*$", re.I,
)
PO_NAZWIE_ROZDZIELNIK = re.compile(r"\s*[:\-\u2013\u2014]")  # „w woj. X: powiat…”: nazwa otwiera nową grupę, nie kończy listę
# Między nazwą województwa a nagłówkiem listy mogą stać tylko znaki rozdzielające i słowa „na terenie”, „w tym”.
PRZYLEGANIE = re.compile(
    rf"{ROZDZIELNIK}*(?:\b(?:w|we|na|terenie|obszarze|tym|szczególności)\b\.?{ROZDZIELNIK}*)*", re.I,
)
NOWE_WOJEWODZTWO = re.compile(r"\b(?:w|we)\s+(?:woj\.|województwie)\s*$", re.I)
SPOJNIK_PRZED =re.compile(r"\b(?:oraz|i|a|także)\s*(?:(?:w|we)\s*)?$", re.I)


def _normalizuj(tekst):
    """Jak `normalizuj` we froncie (powiaty.ts): małe litery, bez polskich znaków, wyrazy rozdzielone spacją."""
    tekst = unicodedata.normalize("NFD", tekst.lower().replace("ł", "l"))
    tekst = "".join(znak for znak in tekst if not unicodedata.combining(znak))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", tekst).split())


def _rdzen(slowo):
    rdzen = slowo.rstrip("aeiouy")
    return rdzen if len(rdzen) >= 3 else slowo


def _odmiana_slowa(zapytanie, slowo):
    """Jak `odmianaSlowa` we froncie: „krakowie” od „krakow”, „chelmskiego” od „chelmski”."""
    if zapytanie == slowo:
        return True
    rdzen = _rdzen(slowo)
    return len(rdzen) >= 3 and zapytanie.startswith(rdzen) and len(zapytanie) - len(rdzen) <= 4


@lru_cache(maxsize=1)
def _slownik_jednostek():
    """Nazwy powiatów i miast na prawach powiatu (kopia frontend-spin/public/teraz/teryt-powiaty.json): nazwa znormalizowana
    na wyrazy i nazwa w formie ze słownika."""
    dane = json.loads(Path(__file__).with_name("jednostki_powiaty.json").read_text(encoding="utf-8"))
    # powiaty ziemskie mają kod 01 do 60, miasta na prawach powiatu 61 i dalej (zgodność z frontem pilnuje test)
    return tuple((_normalizuj(nazwa).split(), nazwa, int(kod[2:]) <= 60) for kod, nazwa in dane["powiaty"])


def _nazwa_ze_slownika(nazwa, dokladnie=False):
    """Forma nazwy ze słownika, gdy `nazwa` (także odmieniona) jest nazwą powiatu albo miasta na prawach powiatu."""
    slowa = _normalizuj(nazwa).split()
    for wzorzec, forma, _ in _slownik_jednostek():
        if len(wzorzec) == len(slowa) and all(
            (q == w) if dokladnie else _odmiana_slowa(q, w) for q, w in zip(slowa, wzorzec)
        ):
            return forma
    return None


def _powiat_ziemski(nazwa):
    """Nazwa (także odmieniona) jest nazwą powiatu ziemskiego ze słownika, nie miasta na prawach powiatu."""
    slowa = _normalizuj(nazwa).split()
    return any(
        ziemski and len(wzorzec) == len(slowa) and all(_odmiana_slowa(q, w) for q, w in zip(slowa, wzorzec))
        for wzorzec, _, ziemski in _slownik_jednostek()
    )


def _nazwa_dozwolona(nazwa, typ):
    """Twardy limit nazw (R38d P1-3): powiat musi być nazwą ze słownika, miasto i gmina to słownik albo 1 do 3 wyrazów z wielkiej
    litery. Nic innego („zalecamy pozostanie w domach”) nie trafia do `miejsce` jako jednostka."""
    slowa = nazwa.split()
    if not 1 <= len(slowa) <= 3:
        return False
    if _nazwa_ze_slownika(nazwa):
        return True
    return bool(typ) and all(len(slowo) >= 2 and slowo[0].isupper() for slowo in slowa)


def _forma_nazwy(nazwa, typ):
    """Zapis nazwy: pisana wielkimi literami wraca do formy ze słownika albo małych liter (powiat) i Wielkich Liter (miasto,
    gmina); reszta bez zmian (R38d P3)."""
    if len(nazwa) > 1 and nazwa == nazwa.upper():
        wielkie = " ".join("-".join(czesc.capitalize() for czesc in slowo.split("-")) for slowo in nazwa.split())
        return _nazwa_ze_slownika(nazwa, dokladnie=True) or (wielkie if typ else nazwa.lower())
    return nazwa


# Słownictwo ściśle rozpoznanego zdania o odbiorcach (Z6P7a). Zdanie jest „ścisłe” tylko wtedy, gdy KAŻDE jego słowo jest
# nazwą województwa, słowem nagłówka jednostek („powiat…”), nazwą jednostki z listy albo stoi poniżej. To biała lista, nie nowa
# reguła rozpoznawania: każde inne słowo („wybranych”, „rejonów”, „część”, „tym”, „godz.”, „północnej”) i każda cyfra zdejmuje
# pewność, więc zakres zostaje otwarty.
SLOWNICTWO_SCISLE = frozenset({
    "alert", "rcb", "ostrzeżenie", "komunikat", "został", "została", "zostało", "wysłany", "wysłana", "wysłano", "skierowano",
    "obowiązuje", "obowiązują", "obejmuje", "dotyczy", "dotyczą", "do", "odbiorców", "mieszkańców", "na", "terenie",
    "w", "we", "woj", "województwie", "województwach", "oraz", "i", "wyłącznie",
})
SLOWO = re.compile(r"[^\W\d_]+")


def _zdanie_scisle(zdanie, listy):
    """Zdanie o odbiorcach ma ściśle rozpoznany kształt: bez cyfr i bez żadnego słowa spoza białej listy."""
    if re.search(r"\d", zdanie):
        return False
    dozwolone = set(SLOWNICTWO_SCISLE)
    for _, nazwy, _, _ in listy:
        for nazwa in nazwy:
            dozwolone.update(slowo.casefold() for slowo in SLOWO.findall(nazwa))
    reszta = NAZWA_MIEJSCOWNIK.sub(" ", NAZWA_WOJ.sub(" ", zdanie))
    return all(
        slowo.casefold() in dozwolone or slowo.casefold().startswith(("powiat", "powiec"))
        for slowo in SLOWO.findall(reszta)
    )


def _bez_znacznikow(miejsce):
    return [linia for linia in (miejsce or "").splitlines() if linia.strip() and not linia.strip().startswith(PREFIKSY_ZNACZNIKOW)]


def _zdanie_odbiorcow(zdanie):
    """Tekst zdania, z którego czytamy zasięg, albo None (R38d P1-3, Z6P6 zasada 3). Zdaniem odbiorców jest nagłówek alertu
    („Alert RCB …”) albo zdanie z czasownikiem wysłania, obowiązywania lub obejmowania („wysłany do odbiorców”, „obowiązuje”,
    „obejmuje”, „dotyczy”); sama wzmianka o mieście lub województwie nim nie jest. Zdanie z czasownikiem zalecenia („zalecamy”,
    „nie powinni”, „unikaj”) też nie, chyba że to nagłówek alertu: czytamy go do pierwszego zalecenia."""
    bez_podmiotu = WYLACZENIE_BEZ_PODMIOTU.match(zdanie)
    zalecenie = REKOMENDACJA.search(zdanie, bez_podmiotu.end() if bez_podmiotu else 0)
    if zalecenie:
        if not (NAGLOWEK_ALERTU.match(zdanie) or bez_podmiotu):
            return None
        zdanie = zdanie[:zalecenie.start()]
    if (NAGLOWEK_ALERTU.match(zdanie) or CZASOWNIK_ODBIORCOW.search(zdanie) or STRUKTURA_LISTY.match(zdanie)
            or CZASOWNIK_WYSLANIA.search(zdanie) and PODMIOT_ALERTU.search(zdanie)):
        return zdanie
    return None


def _nazwa_punktu(punkt):
    """Punkt listy będący samą nazwą jednostki („- pucki”): bez własnego nagłówka typu, nazwy województwa i zalecenia."""
    tekst = PUNKT_LISTY.sub("", punkt).strip(" ;,.")
    if (not tekst or len(tekst.split()) > 3 or NAGLOWEK_JEDNOSTEK.search(tekst) or NAZWA_WOJ.search(tekst)
            or WOJ_MIEJSCOWNIK.search(tekst) or NAZWA_MIEJSCOWNIK.search(tekst) or REKOMENDACJA.search(tekst)):
        return None
    return tekst


def _naglowek_z_punktami(naglowek, punkty):
    """Nagłówek „… powiaty w woj. pomorskim:” z punktami „- pucki”, „- wejherowski” czytamy jak jedno zdanie
    „… powiaty pucki, wejherowski w woj. pomorskim” (Z6P7 pkt 7): nazwy stoją zaraz po nagłówku typu, reszta nagłówka po nich."""
    typ = list(NAGLOWEK_JEDNOSTEK.finditer(naglowek))[-1]
    przed = naglowek[:typ.end()].rstrip()
    reszta = naglowek[typ.end():].strip(" :")
    return f"{przed if przed.endswith(':') else przed + ':'} {', '.join(punkty)}{' ' + reszta if reszta else ''}"


def _zdania_odbiorcow(linie):
    """Zdania o odbiorcach z linii (tekst, czy to punkt listy po „części województwa:”). Punkt listy („- lubelskiego - powiaty: …”)
    i linia „powiaty: …” liczą się tylko po nagłówku zakończonym dwukropkiem; inne punkty to nie odbiorcy. Punkty będące samymi
    nazwami jednostek (elementy `<li>`: „- pucki”) pod nagłówkiem z typem jednostek dopisujemy do tego nagłówka."""
    linie = [linia.strip() for linia in linie]
    otwarta = czesc_listy = False
    i = 0
    while i < len(linie):
        linia = linie[i]
        i += 1
        if otwarta and PUNKT_LISTY.match(linia):
            yield linia, czesc_listy
            continue
        otwarta = czesc_listy = False
        zdania = [zdanie.strip() for zdanie in KONIEC_ZDANIA.split(linia)]
        ostatnie = _zdanie_odbiorcow(zdania[-1]) if zdania else None
        otwiera = bool(ostatnie) and linia.endswith(":")
        punkty = []
        if otwiera and NAGLOWEK_JEDNOSTEK.search(ostatnie) and not CZESC_BEZ_NAZWY.search(ostatnie):
            while i + len(punkty) < len(linie) and PUNKT_LISTY.match(linie[i + len(punkty)]) and _nazwa_punktu(linie[i + len(punkty)]):
                punkty.append(_nazwa_punktu(linie[i + len(punkty)]))
        for numer, zdanie in enumerate(zdania):
            tekst = _zdanie_odbiorcow(zdanie)
            if punkty and numer == len(zdania) - 1:
                tekst = _naglowek_z_punktami(tekst, punkty)
            if tekst and tekst.strip():
                yield tekst.strip(), False
        i += len(punkty)
        if otwiera:
            otwarta, czesc_listy = True, bool(CZESC_BEZ_NAZWY.search(ostatnie))


def zasieg_czesciowy(miejsce, tresc=""):
    """Komunikat obejmuje tylko część województwa: wymienia jednostki węższe (powiaty, gminy, miasta), ma znaczniki wyłączeń
    albo niepełnej listy, mówi o „części województwa” albo w zdaniu o odbiorcach zawęża zasięg do powiatów, gmin lub miast.
    Kod województwa jest wtedy przybliżeniem położenia, nie potwierdzonym zasięgiem alertu. Zdania o odbiorcach sprawdzamy
    osobno, nie cały akapit (słowo „powiatu” w zdaniu z zaleceniem lub o punktach pomocy niczego nie zawęża, R38d, Z6P6)."""
    linie = [linia.strip() for linia in (miejsce or "").splitlines() if linia.strip()]
    if any(not (NAZWA_WOJ.fullmatch(linia) or _caly(linia)) for linia in linie):
        return True
    for tekst, czesc in _zdania_odbiorcow((tresc or "").splitlines()):
        if czesc or CZESC_REGIONU.search(tekst):
            return True
        if TEKST_MIEJSCA.match(tekst) and WZMIANKA_JEDNOSTKI.search(tekst):
            return True
    return False


def _caly(linia):
    zakres = ZAKRES_LINIA.fullmatch(linia)
    return bool(zakres) and zakres.group(2) == "cale"


def adres_karty(adres):
    cel = urlsplit(urljoin(LISTA, adres))
    if (cel.scheme, cel.netloc) != ("https", "www.gov.pl") or not KARTA.fullmatch(cel.path):
        raise BladFormatu("RCB: nieoczekiwany odnośnik karty na liście.")
    return f"https://www.gov.pl{cel.path}"


def parsuj_liste(odpowiedz):
    html = DrzewoHTML(odczytaj(odpowiedz)).korzen
    lista = next(html.znajdz(lambda el: el.ma_klase("art-prev")), None)
    linki = list(lista.znajdz(lambda el: el.ma_klase("title"))) if lista else []
    if not linki:
        raise BladFormatu("RCB: brakuje listy kart komunikatów.")
    adresy = []
    for kontener in linki:
        link = next(kontener.znajdz(lambda el: el.tag == "a" and el.attrs.get("href")), None)
        if link is None:
            raise BladFormatu("RCB: brakuje odnośnika karty komunikatu.")
        adresy.append(adres_karty(link.attrs["href"]))
    licznik = next(html.znajdz(lambda el: el.attrs.get("id") == "js-pagination-pages-count"), None)
    liczby = re.findall(r"\d+", licznik.tekst()) if licznik else []
    return list(dict.fromkeys(adresy)), int(liczby[-1]) if liczby else 1


def _czas(data, godzina):
    if not godzina:
        return None
    return data.replace(hour=int(godzina[1]), minute=int(godzina[2]))


def _klucz_cytatu(tekst):
    return tekst.strip('\"„”«» ').casefold()


def _elementy(segment, typ=""):
    """Nazwy jednostek z fragmentu po nagłówku listy (do następnego nagłówka lub nazwy województwa) i flaga: czy jakiś element
    wyglądał na nazwę, ale nie spełnił limitu nazw (wtedy lista jest niepełna: front nie może powiedzieć „nie ma na liście”)."""
    segment = KONCOWKA_SEGMENTU.sub("", KONIEC_ZDANIA.split(segment, maxsplit=1)[0])
    nazwy, odrzucone = [], False
    for czesc in PODZIAL_ELEMENTOW.split(segment):
        nazwa = czesc.strip(" .-")
        if not nazwa or NAZWA_WOJ.fullmatch(nazwa):
            continue
        if ADRES_SLOWO.search(nazwa):
            continue  # rozpoznany adres („ul. Leśna 12”) to nie jednostka, ale też nie nieczytelna nazwa
        if ADRES.search(nazwa):
            odrzucone = True  # sama cyfra przy nazwie („włodawskim 1”) to element nieczytelny: lista niepełna, nigdy ciche pominięcie
            continue
        if NAZWA_JEDNOSTKI.fullmatch(nazwa) and _nazwa_dozwolona(nazwa, typ):
            nazwy.append(_forma_nazwy(nazwa, typ))
        else:
            odrzucone = True
    return nazwy, odrzucone


def _rozwin_nawiasy(zdanie):
    """„powiaty: A, B (woj. śląskie)” czytamy jak „powiaty: A, B w woj. śląskie”, a „woj. X (powiat Y)” jak „woj. X powiat Y”
    (R38d P2); inne nawiasy zostają."""
    zdanie = NAWIAS_WOJEWODZTWA.sub(r" w woj. \1", zdanie)
    return NAWIAS_JEDNOSTKI.sub(r" \1 ", zdanie)


def _miejscowniki(zdanie):
    """Nazwy województw w miejscowniku (pozycja początku, rdzeń, koniec), także kolejne na liście: „w woj. lubelskim i podkarpackim”."""
    for lista in WOJ_MIEJSCOWNIK.finditer(zdanie):
        for m in NAZWA_MIEJSCOWNIK.finditer(lista.group(0)):
            yield lista.start() + m.start(), m.group(1), lista.start() + m.end()


POPRZEDNI_WYRAZ = re.compile(r"([^\W\d_]+)[  -]$")
SLOWA_WOJEWODZTWA = frozenset({"woj", "województwa", "województwie", "województwo", "województwach"})


def _czlon_nazwy_jednostki(zdanie, m):
    """Nazwa województwa napisana Wielką literą zaraz po innym wyrazie z Wielkiej litery („Wysokie Mazowieckie”) jest członem nazwy
    miejscowości, nie województwem (Z6P7 pkt 8). Pisownia samymi wielkimi literami i tytuł „Województwa Lubelskiego” to nie ten przypadek."""
    nazwa = m.group(0)
    poprzedni = POPRZEDNI_WYRAZ.search(zdanie[:m.start()])
    if not (poprzedni and nazwa[0].isupper() and nazwa[1:].islower()):
        return False
    slowo = poprzedni.group(1)
    return slowo[0].isupper() and slowo[1:].islower() and slowo.casefold() not in SLOWA_WOJEWODZTWA


def _wojewodztwa_zdania(zdanie, poczatek):
    """Wzmianki o województwach w zdaniu jako (pozycja, kod, nominatyw, koniec, część); nazwy w adresie („ul. Lubelska”) pomijamy.
    Zapis nazwy jest znormalizowany (małe litery, miejscownik jako mianownik), także dla zdania pisanego wielkimi literami.
    „Część” oznacza, że przed nazwą stoi „część woj.”, „na południu woj.” itp.; dotyczy też kolejnych nazw na tej samej liście
    („w części woj. lubelskiego i podkarpackiego”)."""
    adres = ADRES.search(zdanie[:poczatek])
    koniec_nazw = adres.start() if adres else poczatek
    nazwy = []
    for m in NAZWA_WOJ.finditer(zdanie):
        if _czlon_nazwy_jednostki(zdanie, m):
            continue
        kod = WOJEWODZTWA[m.group(1).lower()]
        nazwy.append((m.start(), kod, WOJ_RDZEN[kod] + m.group(0)[len(m.group(1)):].lower(), m.end()))
    for poz, rdzen, koniec in _miejscowniki(zdanie):
        kod = WOJEWODZTWA[rdzen.lower()]
        nazwy.append((poz, kod, WOJ_NOMINATYW[kod], koniec))
    wynik = []
    for poz, kod, tekst, koniec in sorted(nazwy):
        if koniec_nazw <= poz < poczatek:
            continue
        if wynik and LACZNIK_WOJEWODZTW.fullmatch(zdanie[wynik[-1][3]:poz]):
            czesc = wynik[-1][4]
        else:
            czesc = bool(CZESC_PRZED_NAZWA.search(zdanie[:poz]))
        wynik.append((poz, kod, tekst, koniec, czesc))
    return wynik


def _jednostki_zdania(zdanie, wojewodztwa, jednostki, czesc_domyslna=False, z_wylaczeniem=False):
    """Dopisuje do `wojewodztwa` i `jednostki` zasięg z jednego zdania o odbiorcach. Jednostka dostaje województwo tylko
    z tego samego wyrażenia: z nazwy tuż po niej („powiecie włodawskim w woj. lubelskim”) albo z nazwy tuż przed jej
    nagłówkiem („woj. lubelskie: powiaty …”, „woj. lubelskim w powiatach …”; to samo województwo obejmuje kolejne nagłówki
    w jednym wyliczeniu, do spójnika „oraz”/„i” albo nowej nazwy województwa). Gdy przypisania nie da się ustalić, jednostka
    zostaje bez województwa.

    Zwraca (zakresy, nieustalone): rodzaj zakresu każdego wspomnianego województwa (R38d, Z6P6, zasada 1) i kody województw
    (None: nie wiadomo którego), których lista jednostek jest niepełna. `lista`: województwo ma jednostki; `czesc`: część
    województwa („w części woj.”, „na południu woj.”, punkt listy po „części województwa:”) albo jednostki, których nie umiemy
    do niego przypisać; `cale`: województwo bez żadnego zawężenia; `lista_otwarta`: jednostki są, ale lista nie jest ściśle zamknięta
    (Z6P7a): zdanie z nieznanymi słowami lub cyframi, „część”, wyłączenie w zdaniu, jednostka inna niż powiat ziemski ze słownika,
    jednostka bez znanego województwa albo pominięty element."""
    naglowki = list(NAGLOWEK_JEDNOSTEK.finditer(zdanie))
    poczatek = naglowki[0].start() if naglowki else len(zdanie)
    zdarzenia = sorted([(poz, "woj", (kod, tekst, koniec, czesc)) for poz, kod, tekst, koniec, czesc in _wojewodztwa_zdania(zdanie, poczatek)]
                       + [(m.start(), "lista", m) for m in naglowki], key=lambda zdarzenie: zdarzenie[0])
    listy = []  # [typ, nazwy, kod województwa albo None, czy pominięto element]
    grupa, koniec_grupy, swieza, lancuch, poprzednia = [], 0, False, None, None
    wspomniane = []  # (kod, część)
    for i, (poz, rodzaj, m) in enumerate(zdarzenia):
        if rodzaj == "woj":
            kod, tekst, koniec, czesc = m
            wojewodztwa.append(tekst)
            wspomniane.append((kod, czesc))
            if i and zdarzenia[i - 1][1] == "lista" and listy:
                opis = zdanie[zdarzenia[i - 1][2].end():poz]
                if PO_JEDNOSTCE.search(opis) and not PO_NAZWIE_ROZDZIELNIK.match(zdanie, koniec):
                    listy[-1][2] = kod  # „powiecie A w woj. X”: województwo należy do jednostki przed nim
                    lancuch = None
                    continue
            # nazwa po wyliczeniu zaczyna nową grupę („…: powiat A; w woj. Y: powiat B”), tak samo „w woj. Y” po samej
            # nazwie („woj. X oraz w woj. Y w powiecie A”: powiat należy do Y); „X i Y - powiaty: …” to jedna grupa
            if not swieza or NOWE_WOJEWODZTWO.search(zdanie[koniec_grupy:poz]):
                grupa = []
            grupa.append(kod)
            swieza, koniec_grupy, lancuch = True, koniec, None
            continue
        przypisane = None
        if swieza:
            # kilka województw przed listą („lubelskiego i podkarpackiego - powiaty: …”): nie wiadomo, które
            if len(set(grupa)) == 1 and PRZYLEGANIE.fullmatch(zdanie[koniec_grupy:m.start()]):
                przypisane = grupa[0]
            swieza, lancuch = False, przypisane
        elif lancuch and poprzednia is not None and not SPOJNIK_PRZED.search(zdanie[poprzednia.end():m.start()]):
            przypisane = lancuch
        else:
            lancuch = None
        poprzednia = m
        koniec = zdarzenia[i + 1][0] if i + 1 < len(zdarzenia) else len(zdanie)
        typ = TYPY_JEDNOSTEK[m.group("typ").lower()]
        nazwy, pominieto = _elementy(zdanie[m.end():koniec], typ)
        listy.append([typ, nazwy, przypisane, pominieto])
    z_nazwami, z_naglowkiem, nieustalone, nieprzypisane = set(), set(), set(), False
    for typ, nazwy, kod, pominieto in listy:
        z_naglowkiem.add(kod)
        if nazwy:
            z_nazwami.add(kod)
        if pominieto:
            nieustalone.add(kod)
        if kod is None and (nazwy or pominieto):
            nieprzypisane = True  # jednostki bez znanego województwa: żadne z wymienionych nie jest „całe”
        for nazwa in nazwy:
            jednostki.append(f"{WOJ_NOMINATYW[kod]}: {typ}{nazwa}" if kod else f"{typ}{nazwa}")
    scisle = not (z_wylaczeniem or czesc_domyslna or nieprzypisane) and _zdanie_scisle(zdanie, listy)

    def zamknieta(kod, czesc):
        wlasne = [lista for lista in listy if lista[2] == kod]
        return scisle and not czesc and kod not in nieustalone and all(
            not typ and not pominieto and all(_powiat_ziemski(nazwa) for nazwa in nazwy) for typ, nazwy, _, pominieto in wlasne
        )

    rodzaje = {}
    for kod, czesc in wspomniane:
        if czesc or czesc_domyslna:
            # „część woj. X, w tym powiat Y” i „wybranych rejonów woj. X”: wyliczenie nie jest wyczerpujące (Z6P7 pkt 2)
            rodzaj = "czesc"
        elif kod in z_nazwami:
            rodzaj = "lista" if zamknieta(kod, czesc) else "lista_otwarta"
        elif kod in z_naglowkiem or nieprzypisane:
            rodzaj = "czesc"
        else:
            rodzaj = "cale"
        rodzaje.setdefault(kod, set()).add(rodzaj)
    # jedno zdanie z częścią województwa wystarcza: lista tego samego województwa z innego członu nie jest wtedy zamknięta
    zakresy = {kod: "czesc" if "czesc" in r else max(r, key=RODZAJ_ZAKRESU.get) for kod, r in rodzaje.items()}
    return zakresy, nieustalone


def _dopisz_zakresy(jednostki, zakresy, nieustalone):
    for kod, rodzaj in zakresy.items():
        jednostki.append(f"{PREFIKS_ZAKRES} {WOJ_NOMINATYW[kod]}: {rodzaj}")
    for kod in sorted(nieustalone, key=lambda kod: kod or ""):
        jednostki.append(LINIA_NIEUSTALONE if kod is None else f"{PREFIKS_NIEUSTALONE} {WOJ_NOMINATYW[kod]}")


def _rodzaj_scalony(rodzaje):
    """Jeden rodzaj z kilku: te same zostają, `lista` z `lista_otwarta` to `lista_otwarta` (suma list, otwarta wygrywa), reszta `czesc`."""
    if len(rodzaje) == 1:
        return next(iter(rodzaje))
    return "lista_otwarta" if rodzaje == {"lista", "lista_otwarta"} else "czesc"


def _scal_zakresy(linie):
    """Linie `miejsce` z jedną linią zakresu na województwo: gdy kilka zdań daje różne rodzaje, wynik to `czesc` (nie twierdzimy
    ani „całe”, ani „nie ma na liście”)."""
    rodzaje, wynik = {}, []
    for linia in linie:
        zakres = ZAKRES_LINIA.fullmatch(linia)
        if zakres is None:
            wynik.append(linia)
            continue
        nazwa = zakres.group(1)
        if nazwa not in rodzaje:
            wynik.append((nazwa,))  # miejsce zakresu: zastąpimy je linią po zebraniu rodzajów
        rodzaje.setdefault(nazwa, set()).add(zakres.group(2))
    return [
        f"{PREFIKS_ZAKRES} {linia[0]}: {_rodzaj_scalony(rodzaje[linia[0]])}"
        if isinstance(linia, tuple) else linia
        for linia in wynik
    ]


def _wylaczenia(wyl, po, domyslne, jednostki):
    """Linie „wyłączone: …” dla fragmentu po słowie wyłączenia; `domyslne`: województwo z części przed wyłączeniem."""
    wylaczone = []
    _, odrzucone_po = _jednostki_zdania(po, [], wylaczone)
    wylaczone = [linia for linia in wylaczone if not linia.startswith(PREFIKSY_ZNACZNIKOW)]
    if NAGLOWEK_JEDNOSTEK.search(po) is None:
        # „z wyłączeniem Chełma”: nazwy bez nagłówka typu, tylko te ze słownika
        wylaczone = [nazwa for nazwa in _elementy(po)[0] if _nazwa_ze_slownika(nazwa)]
    for linia in wylaczone:
        if domyslne and ": " not in linia:
            linia = f"{WOJ_NOMINATYW[domyslne]}: {linia}"
        jednostki.append(PREFIKS_WYLACZONE + linia)
    if wylaczone and not odrzucone_po:
        return
    # „nie dotyczy pozostałych terenów” (słaby znacznik bez żadnej jednostki ani województwa) niczego nie zastrzega
    if wyl.group(0).lower().startswith("nie") and not (NAZWA_WOJ.search(po) or WOJ_MIEJSCOWNIK.search(po) or NAGLOWEK_JEDNOSTEK.search(po)):
        return
    jednostki.append(LINIA_WYLACZENIE_OGOLNE)


def _zdanie_do_zasiegu(zdanie, wojewodztwa, jednostki, czesc_domyslna=False, domyslne=()):
    """Jedno zdanie o odbiorcach. Parser jest zachowawczy (R38d): po „z wyłączeniem”, „z wyjątkiem”, „poza”, „oprócz”, „bez”,
    „nie obowiązuje” jednostki nie są objęte alertem, więc nie trafiają do zasięgu; zapisujemy je osobno jako „wyłączone: …”
    (zasięg zostaje przybliżony), a gdy nie da się ich wskazać, jako „wyłączone: nieokreślone”. Wyłączenie obejmuje tylko swój
    człon: po spójniku z nową nazwą województwa albo po średniku z nowym orzeczeniem zaczyna się dalszy zasięg („w woj.
    pomorskim z wyjątkiem powiatu puckiego, a także w woj. zachodniopomorskim”, Z6P6 pkt 4). Element listy, który nie jest
    nazwą jednostki, daje znacznik „nieustalone”: lista jest wtedy niepełna. Odsyłacze „(1)”, „[2]”, „*” przy nazwach
    zdejmujemy przed czytaniem (Z6P6 pkt 5)."""
    zdanie = _rozwin_nawiasy(ODSYLACZ.sub("", zdanie))
    wyl = WYLACZENIE.search(zdanie)
    zakresy, nieustalone = _jednostki_zdania(
        zdanie[:wyl.start()] if wyl else zdanie, wojewodztwa, jednostki, czesc_domyslna, z_wylaczeniem=bool(wyl))
    _dopisz_zakresy(jednostki, zakresy, nieustalone)
    kody = set(zakresy)
    if not wyl:
        return kody
    reszta = zdanie[wyl.end():]
    granica = KONIEC_WYLACZENIA.search(reszta)
    po, dalej = (reszta[:granica.start()], reszta[granica.end():]) if granica else (reszta, "")
    # województwo wyłączenia bez własnej nazwy: z części przed nim, z dalszej części zdania („Oprócz X alert obejmuje Y w woj. Z”)
    # albo z wcześniejszego zasięgu, jeśli jest dokładnie jedno; w innym razie wyłączenie zostaje bez województwa
    kody_dalej = _zdanie_do_zasiegu(dalej, [], [], czesc_domyslna, domyslne) if dalej.strip() else set()
    kandydaci = kody or kody_dalej or set(domyslne)
    _wylaczenia(wyl, po, next(iter(kandydaci)) if len(kandydaci) == 1 else None, jednostki)
    if dalej.strip():
        kody |= _zdanie_do_zasiegu(dalej, wojewodztwa, jednostki, czesc_domyslna, domyslne)
    return kody


def _jednostki(linie):
    """Linie pola `miejsce`: nazwy województw („lubelskiego”), jednostki węższe, każda z województwem, pod które podpada
    w tym samym wyrażeniu („lubelskie: świdnicki”, „lubelskie: gmina Świdnik”, „dolnośląskie: miasto Świdnica”), zakres każdego
    województwa („zakres: lubelskie: lista”) i znaczniki wyłączeń oraz niepełnej listy. Powiat jest bez przedrostka typu.
    Jednostka bez rozpoznanego województwa zostaje sama („Chełm”): odbiorca czyta ją jako niejednoznaczną, gdy komunikat
    obejmuje więcej niż jedno województwo (recenzja PR #38, R38b P1-1). Czytamy tylko zdania o odbiorcach, każde osobno:
    zalecenie („Omijaj miasto Chełm”) ani punkt pomocy nie dopisują jednostek do zasięgu (R38c P1, R38d P1-3, Z6P6 zasada 3).
    Wyłączenia („z wyłączeniem powiatu X”) trafiają do linii „wyłączone: …”, nie do zasięgu."""
    return _jednostki_z_kontekstem(linie, ())


KODY_NOMINATYW = {nazwa: kod for kod, nazwa in WOJ_NOMINATYW.items()}


def _kody_zakresow(linie):
    """Kody województw z linii „zakres: …” pola `miejsce`."""
    zakresy = (ZAKRES_LINIA.fullmatch(linia) for linia in linie)
    return {KODY_NOMINATYW[zakres.group(1)] for zakres in zakresy if zakres and zakres.group(1) in KODY_NOMINATYW}


def _wzmianka_zasiegu(tekst):
    return bool(WZMIANKA_JEDNOSTKI.search(tekst) or NAZWA_WOJ.search(tekst) or WOJ_MIEJSCOWNIK.search(tekst))


def _niejasna_zmiana(linie):
    """Zdanie z jednostką lub województwem i słowem wyłączenia albo zawężenia („poza”, „tylko”), którego nie rozpoznaliśmy jako
    zdania o odbiorcach: nie zmienia zasięgu, ale wcześniejszy zasięg mógł przez nie zmienić znaczenie (Z6P7, zasada strukturalna)."""
    for linia in linie:
        for zdanie in KONIEC_ZDANIA.split(linia):
            if (zdanie.strip() and _zdanie_odbiorcow(zdanie) is None and not REKOMENDACJA.search(zdanie)
                    and _wzmianka_zasiegu(zdanie) and (WYLACZENIE.search(zdanie) or ZAWEZENIE.search(zdanie))):
                return True
    return False


def _jednostki_z_kontekstem(linie, poprzednie):
    """To samo co `_jednostki`, z zasięgiem ustalonym wcześniej (`poprzednie`: linie `miejsce`, np. z pierwotnego komunikatu przy
    aktualizacji): wyłączenie bez województwa trafia do jedynego znanego województwa (Z6P7 pkt 4), a zdanie nierozpoznane,
    które mogło zmienić znaczenie zasięgu, daje znacznik „nieustalone”."""
    wojewodztwa, jednostki = [], []
    kody = _kody_zakresow(poprzednie)
    for tekst, czesc in _zdania_odbiorcow(linie):
        kody |= _zdanie_do_zasiegu(tekst, wojewodztwa, jednostki, czesc, domyslne=kody if len(kody) == 1 else ())
    if _niejasna_zmiana(linie) and (wojewodztwa or jednostki or poprzednie):
        jednostki.append(LINIA_NIEUSTALONE)
    return _scal_zakresy(list(dict.fromkeys([*wojewodztwa, *jednostki])))


def _zmienia_zasieg(linie, wlasne):
    """Aktualizacja jawnie zmienia zasięg („Od 11:00 alert obejmuje wyłącznie / już tylko powiat chełmski w woj. lubelskim”,
    „ogranicza się do …”): zdanie o odbiorcach ze słowem zmiany i czytelnym nowym zasięgiem z województwem. Nowa lista zastępuje
    wcześniejszą."""
    return any(ZAKRES_LINIA.fullmatch(linia) for linia in wlasne) and any(
        ZMIANA_ZASIEGU.search(tekst) for tekst, _ in _zdania_odbiorcow(linie))


def _zmiana_nieczytelna(linie):
    """Aktualizacja mówi o zawężeniu zasięgu do jednostek, ale nie umiemy odczytać nowego zasięgu z województwem: poprzedni
    zostaje (szerzej, nigdy węziej niż źródło), tylko oznaczony jako nieustalony."""
    return any(ZMIANA_ZASIEGU.search(tekst) and _wzmianka_zasiegu(tekst) for tekst, _ in _zdania_odbiorcow(linie))


def _sekcje(akapity):
    """Sekcje karty jako (aktualizacja, godzina, linie, naglowek): `naglowek` to treść po „Aktualizacja 11:00:” w tej samej linii
    (Z6P7 pkt 6), nie jest w `linie`, żeby tożsamość aktualizacji liczona z `linie` nie zmieniła się dla starszych kart."""
    sekcje = []
    aktualizacja, godzina, linie, naglowek = False, None, [], ""
    for linia in akapity:
        aktualizacja_wiersz = bool(AKTUALIZACJA.match(linia))
        tylko_godzina = GODZINA.fullmatch(linia.rstrip("."))
        separator = re.fullmatch(r"[-\u2013\u2014_ ]{3,}", linia)
        if aktualizacja_wiersz or tylko_godzina or separator:
            if linie or naglowek:
                sekcje.append((aktualizacja, godzina, linie, naglowek))
            aktualizacja, godzina, linie = aktualizacja_wiersz, GODZINA.search(linia), []
            naglowek = linia[NAGLOWEK_AKTUALIZACJI.match(linia).end():].strip() if aktualizacja_wiersz else ""
            naglowek = naglowek if re.search(r"[^\W\d_]{3,}", naglowek) else ""
        else:
            linie.append(linia)
    if linie or naglowek:
        sekcje.append((aktualizacja, godzina, linie, naglowek))
    return sekcje


def _kody_miejsca(miejsce):
    """Kody województw z jednostek objętych alertem: linie z samą nazwą województwa i z nazwą województwa przed dwukropkiem.
    Nazwa województwa w środku nazwy jednostki („miasto Wysokie Mazowieckie”) kodu nie dopisuje (Z6P7 pkt 8); znaczniki
    „wyłączone: …” i „nieustalone: …” też nie."""
    kody = set()
    for linia in _bez_znacznikow(miejsce):
        nazwa = NAZWA_WOJ.fullmatch(linia.partition(": ")[0])
        if nazwa:
            kody.add(WOJEWODZTWA[nazwa.group(1).lower()])
    return sorted(kody)


def _klucz_jednostki(linia):
    """(kod województwa albo None, przedrostek typu, nazwa w formie ze słownika) jednostki z linii `miejsce`."""
    przedrostek, _, reszta = linia.partition(": ")
    nazwa_woj = NAZWA_WOJ.fullmatch(przedrostek)
    kod = WOJEWODZTWA[nazwa_woj.group(1).lower()] if nazwa_woj else None
    if not nazwa_woj:
        reszta = linia
    typ = next((typ for typ in ("miasto ", "gmina ") if reszta.startswith(typ)), "")
    nazwa = reszta[len(typ):]
    return kod, typ, _nazwa_ze_slownika(nazwa) or nazwa.casefold()


def _ta_sama_jednostka(a, b):
    return a[1:] == b[1:] and (a[0] is None or b[0] is None or a[0] == b[0])


def _status_odwolania(tresc, miejsce):
    """Status zdarzenia i linie wyłączeń dla karty (Z6P7, R38g). Odwołanie bez wskazania jednostek („Odwołano alert RCB”, „Brak
    zagrożenia na terenie Polski”) albo obejmujące całą listę jednostek i województw zasięgu to „Odwołane”. Odwołanie jednostek
    ze swojego zdania („Odwołano alert w powiecie puckim”) przy szerszym zasięgu nie odwołuje całego zdarzenia: reszta zostaje
    aktywna, a odwołane jednostki trafiają do linii „wyłączone: …” tej karty."""
    if not ODWOLANIE.search(tresc):
        return Zdarzenie.Status.KOMUNIKAT_OFICJALNY, []
    zdania = [zdanie for linia in tresc.splitlines() for zdanie in KONIEC_ZDANIA.split(linia) if ODWOLANIE.search(zdanie)]
    if not zdania or not all(_wzmianka_zasiegu(zdanie) for zdanie in zdania):
        return Zdarzenie.Status.ODWOLANE, []
    odwolane_woj, odwolane = set(), []
    for zdanie in zdania:
        wojewodztwa, jednostki = [], []
        _jednostki_zdania(_rozwin_nawiasy(ODSYLACZ.sub("", zdanie)), wojewodztwa, jednostki)
        odwolane += [linia for linia in jednostki if not linia.startswith(PREFIKSY_ZNACZNIKOW)]
        odwolane_woj |= {WOJEWODZTWA[NAZWA_WOJ.fullmatch(nazwa).group(1).lower()] for nazwa in wojewodztwa}
    klucze = [_klucz_jednostki(linia) for linia in odwolane]
    zasieg = _bez_znacznikow(miejsce)
    jednostki_zasiegu = [linia for linia in zasieg if not NAZWA_WOJ.fullmatch(linia) and not ZAKRES_LINIA.fullmatch(linia)]
    szerokie = [kod for kod, rodzaj in ((KODY_NOMINATYW[z.group(1)], z.group(2)) for z in map(ZAKRES_LINIA.fullmatch, miejsce.splitlines()) if z)
                if rodzaj in ("cale", "czesc")]
    if not jednostki_zasiegu and not szerokie:
        return Zdarzenie.Status.ODWOLANE, []  # nic nie wiemy o zasięgu poza samym odwołaniem
    pokryte = all(
        _klucz_jednostki(linia)[0] in odwolane_woj or any(_ta_sama_jednostka(_klucz_jednostki(linia), klucz) for klucz in klucze)
        for linia in jednostki_zasiegu
    ) and all(kod in odwolane_woj for kod in szerokie)
    if pokryte:
        return Zdarzenie.Status.ODWOLANE, []
    kody_zasiegu = _kody_miejsca("\n".join(zasieg))
    wylaczone = [PREFIKS_WYLACZONE + (linia if ": " in linia or len(kody_zasiegu) != 1 else f"{WOJ_NOMINATYW[kody_zasiegu[0]]}: {linia}")
                 for linia in odwolane]
    return Zdarzenie.Status.KOMUNIKAT_OFICJALNY, wylaczone or [LINIA_WYLACZENIE_OGOLNE]


def parsuj_karte(odpowiedz, adres):
    html = DrzewoHTML(odczytaj(odpowiedz)).korzen
    karta = next(html.znajdz(lambda el: el.tag == "article" and el.ma_klase("article-area__article")), None)
    if karta is None:
        raise BladFormatu("RCB: brakuje artykułu z komunikatem.")
    tytul = next(karta.znajdz(lambda el: el.tag == "h2"), None)
    data_el = next(karta.znajdz(lambda el: el.ma_klase("event-date")), None)
    edytor = next(karta.znajdz(lambda el: el.ma_klase("editor-content")), None)
    intro = next(karta.znajdz(lambda el: el.ma_klase("intro")), None)
    if not (tytul and data_el and (edytor or intro)):
        raise BladFormatu("RCB: brakuje tytułu, daty lub treści karty.")
    data = datetime.strptime(uprosc(data_el.tekst()), "%d.%m.%Y").replace(tzinfo=WARSZAWA)
    znacznik = data_el if data_el.tag == "time" else next(
        data_el.znajdz(lambda el: el.tag == "time" and el.attrs.get("datetime")), None,
    )
    publikacja = data
    dokladna = False
    if znacznik and "T" in znacznik.attrs.get("datetime", ""):
        publikacja = datetime.fromisoformat(znacznik.attrs["datetime"])
        publikacja = publikacja if publikacja.tzinfo else publikacja.replace(tzinfo=WARSZAWA)
        dokladna = True
    elementy = edytor.znajdz(lambda el: el.tag in {"p", "li", "h3", "h4", "hr"}) if edytor else ()
    akapity = []
    for el in elementy:
        linie_elementu = [uprosc(linia) for linia in ("---" if el.tag == "hr" else el.tekst()).splitlines() if linia.strip()]
        if el.tag == "li" and linie_elementu and not PUNKT_LISTY.match(linie_elementu[0]) and not AKTUALIZACJA.match(linie_elementu[0]):
            linie_elementu[0] = "- " + linie_elementu[0]  # element listy czytamy jak punkt listy (Z6P7 pkt 7)
        akapity.extend(linie_elementu)
    wprowadzenie = uprosc(intro.tekst()) if intro else ""
    sekcje = _sekcje(akapity)
    aktualizacje = [(godz, naglowek, linie) for aktualizacja, godz, linie, naglowek in sekcje if aktualizacja]
    oryginalne = [(godz, linie) for aktualizacja, godz, linie, _ in sekcje if not aktualizacja]
    if not oryginalne and wprowadzenie:
        oryginalne = [(None, [wprowadzenie])]
    if not oryginalne:
        raise BladFormatu("RCB: brakuje treści pierwszego komunikatu.")
    godzina = next((godz for godz, _ in oryginalne if godz), None)
    tekst = list(dict.fromkeys(linia for _, linie in oryginalne for linia in linie))
    if wprowadzenie and not any(_klucz_cytatu(linia) == _klucz_cytatu(wprowadzenie) for linia in tekst):
        tekst.insert(0, wprowadzenie)
    miejsca = _jednostki(tekst)
    wynik = []
    tytul = tytul.tekst()
    grupa = urlsplit(adres).path
    for aktualizacja, godz, naglowek, linie in [(False, godzina, "", tekst), *((True, godz, naglowek, linie) for godz, naglowek, linie in aktualizacje)]:
        czas = _czas(data, godz)
        laczone = miejsca
        tresc_id = "\n".join(linie)
        if naglowek:
            linie = [naglowek, *linie]
        if aktualizacja:
            wlasne = _jednostki_z_kontekstem(linie, miejsca)
            if _zmienia_zasieg(linie, wlasne):
                # jawna zmiana zasięgu zastępuje wcześniejszą listę, także dla kolejnych aktualizacji (Z6P6 pkt 6)
                miejsca = laczone = wlasne
            else:
                laczone = _scal_zakresy(list(dict.fromkeys([*miejsca, *wlasne, *([LINIA_NIEUSTALONE] if _zmiana_nieczytelna(linie) else [])])))
        tresc = "\n".join(linie)
        status, odwolane = _status_odwolania(tresc, "\n".join(laczone))
        laczone = list(dict.fromkeys([*laczone, *odwolane]))
        miejsce = "\n".join(laczone)
        # kod województwa tylko z jednostek objętych alertem: znaczniki „wyłączone: …” i „nieustalone: …” go nie dopisują
        kody = _kody_miejsca(miejsce)
        # wybrane powiaty w województwie: kod 2-cyfrowy to tylko przybliżenie (pewność 0,5); cały region: pewność 1
        pewnosc = (0.5 if zasieg_czesciowy(miejsce, tresc) else 1) if kody else 0
        ident = grupa
        if aktualizacja:
            godzina_id = f"{czas:%H:%M}" if czas else "bez-godziny"
            skrot = sha256(f"{grupa}:{godzina_id}:{(tresc_id or tresc)[:LIMIT_TRESCI]}".encode()).hexdigest()
            ident = f"rcb:aktualizacja:{skrot}"
        wynik.append(wpis(
            ident, tytul, adres, publikacja, tresc=tresc, czas_zrodlowy_at=czas,
            dokladna_godzina_publikacji=dokladna, miejsce=miejsce[:16000], teryt=kody,
            dokladnosc=Wpis.Dokladnosc.WOJEWODZTWO if kody else Wpis.Dokladnosc.BRAK,
            pewnosc_lokalizacji=pewnosc, zdarzenie_id=grupa, status_zdarzenia=status,
        ))
    return wynik


class AdapterRCB(Adapter):
    limit_zadan = 2
    wersja_parsera = "8"

    def parsuj(self, odpowiedz):
        return parsuj_karte(odpowiedz, getattr(self, "adres_aktualnej_karty", self.zrodlo.adres))

    def _zapisz_wpisy(self, pobranie, wpisy, zakres):
        if any(":aktualizacja:" in wpis["zewnetrzny_id"] for wpis in wpisy):
            starsze = pobranie.zrodlo.wpisy.filter(pobranie__odcisk_adresu=pobranie.odcisk_adresu)
            if starsze.filter(usunieto_at__isnull=False, pobranie__wersja_parsera="2").exists():
                # Odcisk starej pozycji po usunięciu wpisu nie pozwala odtworzyć tożsamości aktualizacji.
                zachowane = set(starsze.filter(usunieto_at__isnull=True).values_list("zewnetrzny_id", flat=True))
                wpisy = [wpis for wpis in wpisy if ":aktualizacja:" not in wpis["zewnetrzny_id"]
                         or wpis["zewnetrzny_id"] in zachowane]
        return super()._zapisz_wpisy(pobranie, wpisy, zakres)

    def przeprowadz(self, cykl):
        stan = cykl.stan
        sprawdzenia = stan.setdefault("sprawdzenia_kart", {})
        prog = cykl.start - ODSTEP_KARTY

        def zapamietaj_liste(odpowiedz):
            stan["karty"], _ = parsuj_liste(odpowiedz)
            for adres, czas in list(sprawdzenia.items()):
                if adres not in stan["karty"] and data_iso(czas) <= prog:
                    del sprawdzenia[adres]
            return []

        ma_karty = bool(stan.get("karty"))
        if ma_karty and not sprawdzenia:
            odciski = {self.odcisk_adresu(adres): adres for adres in stan["karty"]}
            for odcisk, czas in self.zrodlo.pobrania.filter(
                odcisk_adresu__in=odciski, pobrano_at__gt=prog,
            ).order_by("pobrano_at").values_list("odcisk_adresu", "pobrano_at"):
                sprawdzenia[odciski[odcisk]] = czas.isoformat()
        cykl.wykonaj(self.zrodlo.adres, parser=zapamietaj_liste, zrzut=False,
                     zawsze_parsuj=True, warunkowo=ma_karty)
        gotowe = [adres for adres in stan["karty"] if adres not in sprawdzenia or data_iso(sprawdzenia[adres]) <= prog]
        if not gotowe:
            return
        adres = min(gotowe, key=lambda adres: data_iso(sprawdzenia[adres]).timestamp() if adres in sprawdzenia else float("-inf"))
        self.adres_aktualnej_karty = adres

        def zapamietaj_probe():
            sprawdzenia[adres] = timezone.now().isoformat()

        cykl.wykonaj_element_kolejki(adres, przesun=zapamietaj_probe, zrzut=False)


class ArchiwumRCB(AdapterRCB):
    minimalny_odstep = 5
    limit_zadan = 1
    pole_proby = "ostatnia_proba_archiwum_at"

    def przeprowadz(self, cykl):
        stan = cykl.stan.setdefault("archiwum", {"strona": 1, "karty": []})
        if stan.get("wersja_parsera") != self.wersja_parsera:
            # nowa wersja parsera: karty zapisane starszą (także zakończone i w połowie przejścia) czytamy od nowa, od strony 1
            # (R38c, P2); wpisy o tym samym identyfikatorze są aktualizowane, nie dublowane
            stan.clear()
            stan.update({"strona": 1, "karty": [], "wersja_parsera": self.wersja_parsera})
        if stan.get("zakonczone"):
            return
        if not stan["karty"] and stan.get("niepobrane") and stan["strona"] > stan.get("stron", 0):
            # lista kart przeczytana do końca, ale część kart nie została pobrana (429, 5xx): ponawiamy tylko je (Z6P6 pkt 7)
            stan["karty"], stan["niepobrane"] = stan["niepobrane"], []
        strona = stan["strona"]
        if stan["karty"]:
            adres = stan["karty"][0]
            self.adres_aktualnej_karty = adres

            def po_karcie():
                stan["karty"].pop(0)
                if not stan["karty"]:
                    stan["strona"] += 1
                    # archiwum jest zakończone dopiero, gdy wszystkie karty zostały pobrane
                    stan["zakonczone"] = strona >= stan["stron"] and not stan.get("niepobrane")

            def odloz():
                niepobrane = stan.setdefault("niepobrane", [])
                if adres not in niepobrane:
                    niepobrane.append(adres)
                po_karcie()

            cykl.wykonaj_element_kolejki(adres, przesun=po_karcie, odloz=odloz, zrzut=False)
        else:
            def zapamietaj(odpowiedz):
                stan["karty"], stan["stron"] = parsuj_liste(odpowiedz)
                return []

            cykl.wykonaj(f"{self.zrodlo.adres}?page={strona}&size=10", parser=zapamietaj,
                         zawsze_parsuj=True, warunkowo=False, zrzut=False)
