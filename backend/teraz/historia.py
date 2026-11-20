"""Historia i zdrowie źródeł dla API „Teraz”.

Zasada: nigdy nie twierdzimy, że czegoś nie było. Brak danych (luka w pobieraniu, obcięta historia wersji, wyczyszczone
wpisy osobowe) zwracamy jawnie jako `brak_danych` z listą źródeł i okresem, a licznik, który wyszedłby zerem przez taką
lukę, to `null`, nie 0.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone as utc_tz

from django.conf import settings
from django.db.models import Count, Max, Min, Q
from django.db.models.functions import TruncDay, TruncHour
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Klasa, Pobranie, Wpis, WylacznikKategorii, Zrodlo
from .zbieranie import LIMIT_WERSJI

MNOZNIK_LUKI = 3
PEWNOSC_MIN = 0.8
MAKS_KUBELKOW = {"dzien": 366, "godzina": 24 * 14}
POLA_CZASU = ("opublikowano_at", "czas_zrodlowy_at")
POLA_WERSJI = (
    "tytul", "tresc", "link", "opublikowano_at", "czas_zrodlowy_at", "dokladna_godzina_publikacji",
    "miejsce", "teryt", "szerokosc", "dlugosc", "bbox", "dokladnosc", "pewnosc_lokalizacji",
)
KOD_WSTRZYMANIA = "dostep_wstrzymany"
KOD_HTTP = "blad_http"
KOD_OGOLNY = "blad_zrodla"


class Powod:
    LUKA_POBIERANIA = "luka_pobierania"
    HISTORIA_NIEPELNA = "historia_niepelna"
    LUKA_RETENCJI = "luka_retencji"


# ---------------------------------------------------------------- zdrowie źródeł

def kod_bledu(zrodlo):
    """Ogólny kod ostatniego błędu. Wewnętrzny tekst błędu (`ostatni_blad`) nigdy nie trafia do API."""
    if zrodlo.blokada_dostepu:
        return KOD_WSTRZYMANIA
    if not (zrodlo.ostatni_blad or zrodlo.kolejne_bledy):
        return None
    if zrodlo.ostatni_blad.startswith("Dostęp wstrzymany"):
        return KOD_WSTRZYMANIA
    if re.fullmatch(r"http_[0-9]{3}", zrodlo.ostatni_blad):
        return KOD_HTTP
    return KOD_OGOLNY


def prog_luki(czestotliwosc_s):
    return timedelta(seconds=MNOZNIK_LUKI * czestotliwosc_s)


def luka_zrodla(zrodlo, teraz):
    """Brak sukcesu dłużej niż 3 x częstotliwość albo brak jakiegokolwiek sukcesu."""
    sukces = zrodlo.ostatni_sukces_at
    return sukces is None or teraz - sukces > prog_luki(zrodlo.czestotliwosc_s)


def udane_pobrania():
    """Pobrania zakończone sukcesem (także 304); błędne mają pusty hash treści."""
    return Pobranie.objects.exclude(hash_tresci="")


def wylaczone_warstwy():
    return set(WylacznikKategorii.objects.filter(aktywny=True, warstwa__isnull=False)
               .values_list("warstwa", flat=True))


def zrodla_publiczne(wylaczone=None):
    """Bramka publikacji źródeł: tryb publiczny i warstwa bez aktywnego wyłącznika (jak w /warstwy/)."""
    wylaczone = wylaczone_warstwy() if wylaczone is None else wylaczone
    return Zrodlo.objects.filter(tryb=Zrodlo.Tryb.PUBLICZNY).exclude(warstwa__in=wylaczone).order_by("slug")


# ---------------------------------------------------------------- retencja

def prog_retencji_osobowej(teraz=None):
    return (teraz or timezone.now()) - timedelta(days=settings.TERAZ_RETENCJA_OSOBOWE_DNI)


def okresy_luki_retencji(do_czasu, teraz=None):
    """Okresy do `do_czasu`, w których wpisy osobowe (a także wyczyszczone na żądanie) mogły zniknąć: lista (od, do).

    Wpisy osobowe są kasowane po TERAZ_RETENCJA_OSOBOWE_DNI, więc historia starsza niż próg jest dla nich zawsze niepełna
    (od = None: początku nie znamy). Wpisy wyczyszczone mają okres od najstarszego do najnowszego z nich.
    """
    publiczne = Wpis.objects.filter(zrodlo__tryb=Zrodlo.Tryb.PUBLICZNY)
    okresy = []
    prog = min(do_czasu, prog_retencji_osobowej(teraz))
    if publiczne.filter(opublikowano_at__lt=prog).exists():
        okresy.append((None, prog))
    wyczyszczone = publiczne.filter(usunieto_at__isnull=False, opublikowano_at__lte=do_czasu).aggregate(
        od=Min("opublikowano_at"), do=Max("opublikowano_at"))
    if wyczyszczone["od"] is not None:
        okresy.append((wyczyszczone["od"], wyczyszczone["do"]))
    return okresy


def luka_retencji(do_czasu, teraz=None):
    return bool(okresy_luki_retencji(do_czasu, teraz))


# ---------------------------------------------------------------- stan na moment

@dataclass
class StanNa:
    pola: dict = field(default_factory=dict)
    biezaca: bool = True
    obowiazywala_do: datetime | None = None


def _pola_wersji(wersja):
    pola = {}
    for nazwa in POLA_WERSJI:
        if nazwa not in wersja:
            continue
        wartosc = wersja[nazwa]
        if nazwa in POLA_CZASU and isinstance(wartosc, str):
            wartosc = parse_datetime(wartosc)
        pola[nazwa] = wartosc
    return pola


def stan_wpisu_na(wpis, na):
    """Wersja wpisu obowiązująca w chwili `na` albo None, gdy jej nie znamy.

    `wersje` to lista poprzednich wersji, każda z czasem zastąpienia (`zastapiono_at`). W chwili `na` obowiązywała
    pierwsza wersja zastąpiona dopiero po `na`; jeśli żadna, obowiązuje bieżąca. W chwili samego zastąpienia obowiązuje już
    nowa wersja. Lista jest obcinana do LIMIT_WERSJI, więc przy pełnej liście nie wiemy, co było przed najstarszą z nich.
    """
    wersje = wpis.wersje or []
    for numer, wersja in enumerate(wersje):
        zastapiono = parse_datetime(wersja.get("zastapiono_at") or "")
        if zastapiono is None or zastapiono <= na:
            continue
        if numer == 0 and len(wersje) >= LIMIT_WERSJI:
            return None
        return StanNa(_pola_wersji(wersja), biezaca=False, obowiazywala_do=zastapiono)
    return StanNa()


def wersja_dostepna_publicznie(wpis, stan):
    """Starszych wersji wpisów wrażliwych nie pokazujemy: decyzja redakcji dotyczy tylko wersji bieżącej."""
    return stan.biezaca or wpis.klasa == Klasa.ZWYKLY


@dataclass
class WpisyNa:
    queryset: object
    nieznane: list = field(default_factory=list)


def wpisy_na(na):
    """Wpisy publiczne wg dzisiejszej bramki, opublikowane do `na`.

    Czas publikacji bywa zmieniany w nowej wersji (np. ponowne wydanie ostrzeżenia), więc obok wpisów z bieżącym czasem
    do `na` sprawdzamy te pobrane przed `na`, a opublikowane (w wersji bieżącej) po nim: rozstrzyga wersja z `wersje`.
    Wpisy, których wersji z chwili `na` nie da się odtworzyć, nie są na liście, tylko w `nieznane`.
    """
    publiczne = Wpis.objects.publiczne()
    dodatkowe, nieznane = [], []
    pozniejsze = publiczne.filter(opublikowano_at__gt=na, pobrano_at__lte=na).select_related("zrodlo")
    for wpis in pozniejsze.iterator():
        stan = stan_wpisu_na(wpis, na)
        if stan is None or stan.biezaca:
            if stan is None or not wpis.wersje:
                nieznane.append(wpis)
            continue
        opublikowano = stan.pola.get("opublikowano_at")
        if opublikowano is not None and opublikowano <= na:
            dodatkowe.append(wpis.pk)
    wybrane = publiczne.filter(Q(opublikowano_at__lte=na) | Q(pk__in=dodatkowe))
    return WpisyNa(wybrane, nieznane)


def brak_danych_na(na, wynik, teraz=None):
    """Lista `brak_danych` dla stanu na moment: źródła bez świeżego sukcesu, obcięta historia, luka retencji."""
    teraz = teraz or timezone.now()
    brak = []
    zrodla = list(zrodla_publiczne())
    ostatnie = dict(udane_pobrania().filter(pobrano_at__lte=na, zrodlo__in=zrodla)
                    .values_list("zrodlo_id").annotate(Max("pobrano_at")))
    for zrodlo in zrodla:
        sukces = ostatnie.get(zrodlo.pk)
        if sukces is None or na - sukces > prog_luki(zrodlo.czestotliwosc_s):
            brak.append({"powod": Powod.LUKA_POBIERANIA, "zrodla": [zrodlo.slug], "od": sukces, "do": na})
    if wynik.nieznane:
        brak.append({
            "powod": Powod.HISTORIA_NIEPELNA,
            "zrodla": sorted({wpis.zrodlo.slug for wpis in wynik.nieznane}),
            "od": min(wpis.pobrano_at for wpis in wynik.nieznane), "do": na,
        })
    for od, do in okresy_luki_retencji(na, teraz):
        brak.append({"powod": Powod.LUKA_RETENCJI, "zrodla": [], "od": od, "do": do})
    return brak


# ---------------------------------------------------------------- oś czasu

def kubelki(od, do, krok):
    """Przedziały [początek, koniec) o stałym kroku w strefie projektu (doba lokalna albo godzina)."""
    strefa = timezone.get_default_timezone()
    wynik = []
    if krok == "dzien":
        dzien = od.astimezone(strefa).date()
        while True:
            poczatek = datetime.combine(dzien, time.min, tzinfo=strefa)
            if poczatek > do:
                break
            koniec = datetime.combine(dzien + timedelta(days=1), time.min, tzinfo=strefa)
            wynik.append((poczatek, koniec))
            dzien += timedelta(days=1)
            if len(wynik) > MAKS_KUBELKOW["dzien"]:
                break
    else:
        poczatek = od.astimezone(utc_tz.utc).replace(minute=0, second=0, microsecond=0)
        while poczatek <= do:
            wynik.append((poczatek, poczatek + timedelta(hours=1)))
            poczatek += timedelta(hours=1)
            if len(wynik) > MAKS_KUBELKOW["godzina"]:
                break
    return wynik


def _obcinanie(krok):
    strefa = timezone.get_default_timezone()
    return TruncDay("opublikowano_at", tzinfo=strefa) if krok == "dzien" else TruncHour("opublikowano_at", tzinfo=strefa)


def _licz_po_kubelkach(queryset, krok):
    return dict(queryset.annotate(kubelek=_obcinanie(krok)).values_list("kubelek").annotate(n=Count("pk")))


def _pokrycie_zrodla(zrodlo, przedzialy, krok, teraz):
    """Zbiór początków przedziałów, w których źródło nie miało pokrycia pobraniami.

    Przedział jest pokryty, gdy w nim samym było udane pobranie albo ostatnie wcześniejsze było nie starsze niż 3 x
    częstotliwość przed jego końcem (przedział z przyszłości ścinamy do chwili obecnej). Wewnątrz przedziału z
    pobraniami nie szukamy dziur: dokładność to jeden przedział.
    """
    prog = prog_luki(zrodlo.czestotliwosc_s)
    poczatek, koniec = przedzialy[0][0], przedzialy[-1][1]
    pobrania = udane_pobrania().filter(zrodlo=zrodlo)
    ostatnie = pobrania.filter(pobrano_at__lt=poczatek).aggregate(m=Max("pobrano_at"))["m"]
    strefa = timezone.get_default_timezone()
    obcinanie = (TruncDay("pobrano_at", tzinfo=strefa) if krok == "dzien" else TruncHour("pobrano_at", tzinfo=strefa))
    w_kubelkach = dict(pobrania.filter(pobrano_at__gte=poczatek, pobrano_at__lt=koniec)
                       .annotate(kubelek=obcinanie).values_list("kubelek").annotate(m=Max("pobrano_at")))
    niepokryte = set()
    for start, kon in przedzialy:
        if start in w_kubelkach:
            ostatnie = w_kubelkach[start]
        elif ostatnie is None or ostatnie + prog < min(kon, teraz):
            niepokryte.add(start)
    return niepokryte


def os_czasu(od, do, krok, teraz=None):
    """Histogram liczby wpisów w czasie wraz z jawnymi lukami.

    Liczymy wpisy publiczne wg dzisiejszej bramki, których publicznie pokazywana pewność lokalizacji wynosi co najmniej 0,8
    (klasy wrażliwe pokazujemy bez lokalizacji, więc nie wchodzą do histogramu). Osobno liczymy wpisy wrażliwe czekające
    w przeglądzie: to stan bieżący, nie historyczny, bo decyzja zmienia status wpisu.
    """
    teraz = teraz or timezone.now()
    do = min(do, teraz)
    przedzialy = kubelki(od, do, krok)
    if not przedzialy:
        return {"kubelki": [], "brak_danych": [], "luka_retencji": False, "od": od, "do": do}
    poczatek, koniec = przedzialy[0][0], przedzialy[-1][1]
    zakres = {"opublikowano_at__gte": poczatek, "opublikowano_at__lt": koniec}
    potwierdzone = Wpis.objects.publiczne().filter(klasa=Klasa.ZWYKLY, pewnosc_lokalizacji__gte=PEWNOSC_MIN, **zakres)
    liczby = _licz_po_kubelkach(potwierdzone, krok)
    przeglad = _licz_po_kubelkach(Wpis.objects.w_przegladzie().filter(**zakres), krok)
    wyczyszczone = _licz_po_kubelkach(
        Wpis.objects.filter(usunieto_at__isnull=False, zrodlo__tryb=Zrodlo.Tryb.PUBLICZNY, **zakres), krok)
    prog = prog_retencji_osobowej(teraz)

    zrodla = list(zrodla_publiczne())
    niepokryte = {zrodlo.slug: _pokrycie_zrodla(zrodlo, przedzialy, krok, teraz) for zrodlo in zrodla}
    wynik, luki = [], {zrodlo.slug: [] for zrodlo in zrodla}
    for start, kon in przedzialy:
        brak_zrodel = sorted(slug for slug, zbior in niepokryte.items() if start in zbior)
        for slug in brak_zrodel:
            luki[slug].append((start, kon))
        luka = start < prog or wyczyszczone.get(start, 0) > 0
        liczba = liczby.get(start, 0)
        wynik.append({
            "od": start, "do": kon,
            # zero przy luce nie jest zerem: nie wiemy, czy czegoś nie było
            "liczba": None if liczba == 0 and (luka or brak_zrodel) else liczba,
            "w_przegladzie": przeglad.get(start, 0),
            "luka_retencji": luka,
            "luka_zrodel": brak_zrodel,
        })
    brak = []
    for slug, lista in luki.items():
        for poczatek_luki, koniec_luki in _scal(lista):
            brak.append({"powod": Powod.LUKA_POBIERANIA, "zrodla": [slug], "od": poczatek_luki, "do": koniec_luki})
    if poczatek < prog:
        brak.append({"powod": Powod.LUKA_RETENCJI, "zrodla": [], "od": poczatek, "do": min(koniec, prog)})
    return {"od": poczatek, "do": koniec, "kubelki": wynik, "brak_danych": brak,
            "luka_retencji": any(k["luka_retencji"] for k in wynik)}


def _scal(przedzialy):
    scalone = []
    for start, koniec in przedzialy:
        if scalone and scalone[-1][1] == start:
            scalone[-1] = (scalone[-1][0], koniec)
        else:
            scalone.append((start, koniec))
    return scalone
