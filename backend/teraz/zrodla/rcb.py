import re
from datetime import datetime, timedelta
from hashlib import sha256
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
NAZWA_WOJ = re.compile(r"(?<![\w-])(" + "|".join(WOJEWODZTWA) + r")(?:ie(?:go|m)?|ich)\b", re.I)
# „w woj. lubelskim”: miejscownik tylko po „woj.” lub „województwie”, bo „w powiecie lubelskim” to powiat, nie województwo
WOJ_MIEJSCOWNIK = re.compile(r"\b(?:woj\.|województwie)\s+(" + "|".join(WOJEWODZTWA) + r")im\b", re.I)
TEKST_MIEJSCA = re.compile(r"^alert rcb .*?(?:odbiorc|teren|województw|powiat)|^[-•]\s", re.I)
# Nagłówek listy jednostek: z dwukropkiem („powiaty: A, B”) albo bez („w powiatach A i B”, „powiat świdnicki”).
NAGLOWEK_JEDNOSTEK = re.compile(
    r"(?:\b(?:w|we)\s+)?\b(?P<typ>powiat|powiec|gmin|miast)[^\W\d_]*(?:\s*:\s*|\s+(?=[^\W\d_]))", re.I,
)
NAGLOWEK_WOJEWODZTW = re.compile(r"\bwojewództw(?:o|a)?\s*:", re.I)
TYPY_JEDNOSTEK = {"powiat": "", "powiec": "", "gmin": "gmina ", "miast": "miasto "}
KONIEC_ZDANIA = re.compile(r"(?<!woj)\.(?:\s|$)", re.I)
KONCOWKA_SEGMENTU = re.compile(
    r"[\s,;:\-\u2013\u2014]*(?:\b(?:oraz|i|a|także|w|we|woj|województwie|województwa|województwo)\b\.?[\s,;:\-\u2013\u2014]*)*$", re.I,
)
PODZIAL_ELEMENTOW = re.compile(r"[,;]|\s+(?:i|oraz)\s+", re.I)
ADRES = re.compile(r"\d|\b(?:ul(?:ica|icy|icę)?|al(?:eja|ei|eję)?|plac|os(?:iedle)?|nr)\b", re.I)
NAZWA_JEDNOSTKI = re.compile(r"[^\W\d_]+(?:[ -][^\W\d_]+){0,4}")
ODSTEP_KARTY = timedelta(minutes=10)
CZESC_REGIONU = re.compile(r"\bczęś(?:ć|ci)\s+(?:woj\.|województw)", re.I)
WZMIANKA_JEDNOSTKI = re.compile(r"\b(?:powiat|powiec|gmin|miast)[^\W\d_]*", re.I)
ROZDZIELNIK = r"[\s,;:\-\u2013\u2014]"
# Zdanie z zaleceniem, nie z odbiorcami („Omijaj miasto Chełm”).
REKOMENDACJA = re.compile(
    r"^\W*(?:nie|omijaj|unikaj|zachowaj|stosuj|pozostań|zostań|ogranicz|udaj|zabezpiecz|sprawdź|prosimy|zalecamy|należy|bądź)\b", re.I,
)
# Zdanie o odbiorcach: nagłówek („woj.”, „odbiorcy”, „dla…”), „w powiecie/gminie/mieście…” albo „powiaty: …”.
KONTEKST_ODBIORCOW = re.compile(
    r"\bwoj\.|\bwojewództw|\bodbiorc|\bdla\b|\b(?:w|we)\s+(?:powiat|powiec|gmin|miast)|\b(?:powiat|powiec|gmin|miast)[^\W\d_]*\s*:", re.I,
)
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


def zasieg_czesciowy(miejsce, tresc=""):
    """Komunikat obejmuje tylko część województwa: wymienia jednostki węższe (powiaty, gminy, miasta), mówi o „części
    województwa” albo w zdaniu o odbiorcach zawęża zasięg do powiatów, gmin lub miast. Kod województwa jest wtedy
    przybliżeniem położenia, nie potwierdzonym zasięgiem alertu."""
    jednostki = [linia.strip() for linia in (miejsce or "").splitlines() if linia.strip()]
    if any(not NAZWA_WOJ.fullmatch(nazwa) for nazwa in jednostki) or CZESC_REGIONU.search(tresc or ""):
        return True
    return any(TEKST_MIEJSCA.match(linia) and WZMIANKA_JEDNOSTKI.search(linia) for linia in (tresc or "").splitlines())


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


def _elementy(segment):
    """Nazwy jednostek z fragmentu po nagłówku listy (do następnego nagłówka lub nazwy województwa)."""
    segment = KONCOWKA_SEGMENTU.sub("", KONIEC_ZDANIA.split(segment, maxsplit=1)[0])
    for czesc in PODZIAL_ELEMENTOW.split(segment):
        nazwa = czesc.strip(" .-")
        if NAZWA_JEDNOSTKI.fullmatch(nazwa) and not ADRES.search(nazwa) and not NAZWA_WOJ.fullmatch(nazwa):
            yield nazwa


def _odbiorcy(zdanie):
    """Zdanie określa odbiorców alertu (nagłówek, „dla…”, „w powiecie…”, „woj. …”), a nie jest zaleceniem („Omijaj miasto
    Chełm”): tylko z takich zdań czytamy zasięg (recenzja PR #38, R38c P1)."""
    return not REKOMENDACJA.match(zdanie) and bool(TEKST_MIEJSCA.match(zdanie) or KONTEKST_ODBIORCOW.search(zdanie))


def _wojewodztwa_zdania(zdanie, poczatek):
    """Wzmianki o województwach w zdaniu jako (pozycja, kod, nominatyw, koniec); nazwy w adresie („ul. Lubelska”) pomijamy."""
    adres = ADRES.search(zdanie[:poczatek])
    koniec_nazw = adres.start() if adres else poczatek
    nazwy = [(m.start(), m.group(1), m.group(0), m.end()) for m in NAZWA_WOJ.finditer(zdanie)]
    nazwy += [(m.start(1), m.group(1), m.group(1) + "ie", m.end()) for m in WOJ_MIEJSCOWNIK.finditer(zdanie)]
    return [(poz, WOJEWODZTWA[rdzen.lower()], tekst, koniec) for poz, rdzen, tekst, koniec in nazwy
            if poz < koniec_nazw or poz >= poczatek]


def _jednostki_zdania(zdanie, wojewodztwa, jednostki):
    """Dopisuje do `wojewodztwa` i `jednostki` zasięg z jednego zdania o odbiorcach. Jednostka dostaje województwo tylko
    z tego samego wyrażenia: z nazwy tuż po niej („powiecie włodawskim w woj. lubelskim”) albo z nazwy tuż przed jej
    nagłówkiem („woj. lubelskie: powiaty …”, „woj. lubelskim w powiatach …”; to samo województwo obejmuje kolejne nagłówki
    w jednym wyliczeniu, do spójnika „oraz”/„i” albo nowej nazwy województwa). Nazwa województwa, która nie przylega do
    żadnej jednostki, oznacza całe województwo. Gdy przypisania nie da się ustalić, jednostka zostaje bez województwa."""
    naglowki = list(NAGLOWEK_JEDNOSTEK.finditer(zdanie))
    poczatek = naglowki[0].start() if naglowki else len(zdanie)
    zdarzenia = sorted([(poz, "woj", (kod, tekst, koniec)) for poz, kod, tekst, koniec in _wojewodztwa_zdania(zdanie, poczatek)]
                       + [(m.start(), "lista", m) for m in naglowki], key=lambda zdarzenie: zdarzenie[0])
    listy = []  # [typ, nazwy, kod województwa albo None]
    grupa, koniec_grupy, swieza, lancuch, poprzednia = [], 0, False, None, None
    wspomniane, z_jednostkami = [], set()
    for i, (poz, rodzaj, m) in enumerate(zdarzenia):
        if rodzaj == "woj":
            kod, tekst, koniec = m
            wojewodztwa.append(tekst)
            wspomniane.append((kod, tekst))
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
        listy.append([TYPY_JEDNOSTEK[m.group("typ").lower()], list(_elementy(zdanie[m.end():koniec])), przypisane])
    for typ, nazwy, kod in listy:
        z_jednostkami.add(kod)
        for nazwa in nazwy:
            jednostki.append(f"{WOJ_NOMINATYW[kod]}: {typ}{nazwa}" if kod else f"{typ}{nazwa}")
    if CZESC_REGIONU.search(zdanie) and any(z_jednostkami - {None}):
        # „części woj. X” obok jednostek z innego województwa: X nie może wyglądać na całe województwo
        for kod, tekst in wspomniane:
            if kod not in z_jednostkami:
                jednostki.append(f"{WOJ_NOMINATYW[kod]}: część województwa")


def _jednostki(linie):
    """Linie pola `miejsce`: nazwy województw („lubelskiego”) i jednostki węższe, każda z województwem, pod które
    podpada w tym samym wyrażeniu: „lubelskie: świdnicki”, „lubelskie: gmina Świdnik”, „dolnośląskie: miasto Świdnica”.
    Powiat jest bez przedrostka typu. Jednostka bez rozpoznanego województwa zostaje sama („Chełm”): odbiorca czyta ją jako
    niejednoznaczną, gdy komunikat obejmuje więcej niż jedno województwo (recenzja PR #38, R38b P1-1). Czytamy tylko
    zdania o odbiorcach, każde osobno: zalecenie („Omijaj miasto Chełm”) nie dopisuje jednostek do zasięgu (R38c P1)."""
    wojewodztwa, jednostki = [], []
    for linia in linie:
        for zdanie in KONIEC_ZDANIA.split(linia):
            zdanie = zdanie.strip()
            if zdanie and _odbiorcy(zdanie):
                _jednostki_zdania(zdanie, wojewodztwa, jednostki)
    return list(dict.fromkeys([*wojewodztwa, *jednostki]))


def _sekcje(akapity):
    sekcje = []
    aktualizacja, godzina, linie = False, None, []
    for linia in akapity:
        aktualizacja_wiersz = bool(AKTUALIZACJA.match(linia))
        tylko_godzina = GODZINA.fullmatch(linia.rstrip("."))
        separator = re.fullmatch(r"[-\u2013\u2014_ ]{3,}", linia)
        if aktualizacja_wiersz or tylko_godzina or separator:
            if linie:
                sekcje.append((aktualizacja, godzina, linie))
            aktualizacja, godzina, linie = aktualizacja_wiersz, GODZINA.search(linia), []
        else:
            linie.append(linia)
    if linie:
        sekcje.append((aktualizacja, godzina, linie))
    return sekcje


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
    akapity = [linia for el in elementy for linia in ("---" if el.tag == "hr" else el.tekst()).splitlines()]
    akapity = [uprosc(linia) for linia in akapity if linia.strip()]
    wprowadzenie = uprosc(intro.tekst()) if intro else ""
    sekcje = _sekcje(akapity)
    aktualizacje = [(godz, linie) for aktualizacja, godz, linie in sekcje if aktualizacja]
    oryginalne = [(godz, linie) for aktualizacja, godz, linie in sekcje if not aktualizacja]
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
    for aktualizacja, godz, linie in [(False, godzina, tekst), *((True, godz, linie) for godz, linie in aktualizacje)]:
        czas = _czas(data, godz)
        miejsce = "\n".join(dict.fromkeys([*miejsca, *_jednostki(linie)]))
        kody = sorted({WOJEWODZTWA[nazwa.lower()] for nazwa in NAZWA_WOJ.findall(miejsce)})
        tresc = "\n".join(linie)
        # wybrane powiaty w województwie: kod 2-cyfrowy to tylko przybliżenie (pewność 0,5); cały region: pewność 1
        pewnosc = (0.5 if zasieg_czesciowy(miejsce, tresc) else 1) if kody else 0
        ident = grupa
        if aktualizacja:
            godzina_id = f"{czas:%H:%M}" if czas else "bez-godziny"
            skrot = sha256(f"{grupa}:{godzina_id}:{tresc[:LIMIT_TRESCI]}".encode()).hexdigest()
            ident = f"rcb:aktualizacja:{skrot}"
        status = Zdarzenie.Status.ODWOLANE if ODWOLANIE.search(tresc) else Zdarzenie.Status.KOMUNIKAT_OFICJALNY
        wynik.append(wpis(
            ident, tytul, adres, publikacja, tresc=tresc, czas_zrodlowy_at=czas,
            dokladna_godzina_publikacji=dokladna, miejsce=miejsce[:16000], teryt=kody,
            dokladnosc=Wpis.Dokladnosc.WOJEWODZTWO if kody else Wpis.Dokladnosc.BRAK,
            pewnosc_lokalizacji=pewnosc, zdarzenie_id=grupa, status_zdarzenia=status,
        ))
    return wynik


class AdapterRCB(Adapter):
    limit_zadan = 2
    wersja_parsera = "4"

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
        strona = stan["strona"]
        if stan["karty"]:
            adres = stan["karty"][0]
            self.adres_aktualnej_karty = adres

            def przesun():
                stan["karty"].pop(0)
                if not stan["karty"]:
                    stan["strona"] += 1
                    stan["zakonczone"] = strona >= stan["stron"]

            cykl.wykonaj_element_kolejki(adres, przesun=przesun, zrzut=False)
        else:
            def zapamietaj(odpowiedz):
                stan["karty"], stan["stron"] = parsuj_liste(odpowiedz)
                return []

            cykl.wykonaj(f"{self.zrodlo.adres}?page={strona}&size=10", parser=zapamietaj,
                         zawsze_parsuj=True, warunkowo=False, zrzut=False)
