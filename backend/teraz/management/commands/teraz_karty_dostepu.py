"""Szkice kart dostępu dla zbieraczy Teraz.

Polecenie tworzy (idempotentnie) `news.Source` i `news.SourceAccessInstruction` w statusie DRAFT albo
CONTACT_REQUIRED. Nigdy niczego nie zatwierdza: zatwierdzenie karty to decyzja człowieka w panelu administratora
po przeczytaniu pola `evidence`. Do czasu zatwierdzenia bramka `scraper.access_gate` nie przepuści żadnego żądania.

Opcja `--powiaz` działa dopiero po zatwierdzeniu: dla źródeł z zatwierdzoną, ważną kartą włącza `news.Source`
i wiąże go ze źródłem Teraz (`Zrodlo.zrodlo_dostepu`), bez czego zbieracz nie ruszy.

Podstawa treści kart: Z0-PRAWNIK (17.11.2026, aktualizacja 18.11.2026) i Z0-DOSTEP (18.11.2026).
"""
from math import ceil
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from news.models import Source, SourceAccessInstruction, SourceType
from scraper.access_gate import reviewed_instruction_for_endpoint

from ...models import Zrodlo
from ...zbieranie import KANALY, AdapterTestowy
from ...zrodla import cert_pl, emsc, firms, gdacs, gios, imgw_hydro, imgw_meteo, pse_osp, rcb, usgs
from ...zrodla.rejestr import ADAPTERY
from ...zrodla.wspolne import POLSKA
from ...transport import BAZA_FIRMS, SEGMENT_KLUCZA_FIRMS

Status = SourceAccessInstruction.Status
Scope = SourceAccessInstruction.Scope

ZAPAS = 1.5
BRAK_OCENY = "Brak wzmianki w Z0-PRAWNIK: wymaga przeglądu przed zatwierdzeniem."
IMGW_ZRODLO = "Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej - Państwowy Instytut Badawczy"
IMGW_PRZETWORZENIE = ("Dane Instytutu Meteorologii i Gospodarki Wodnej - Państwowego Instytutu Badawczego "
                      "zostały przetworzone")
OBSZAR_FIRMS = ",".join(map(str, POLSKA))
SCIEZKA_FIRMS = urlsplit(BAZA_FIRMS).path


def _sciezka(adres):
    return urlsplit(adres).path


# Jeden wpis na źródło z rejestru adapterów. `endpoint` i `wzorce` pochodzą ze stałych w kodzie adapterów.
# `zadania` to liczba żądań na okres `Zrodlo.czestotliwosc_s` (domyślnie `limit_zadan` adaptera).
KARTY = {
    "rcb": dict(
        status=Status.DRAFT, zakres=Scope.CONTENT, endpoint="https://www.gov.pl/web/rcb",
        wzorce=[_sciezka(rcb.LISTA), "/web/rcb/{token}"], odstep=5, dodatek=1200,
        terms_url="https://www.gov.pl/web/gov/prawa-autorskie",
        werdykt="Publicznie tak, także Pro i API (Z0-PRAWNIK, pewność prawdopodobna, ryzyko niskie).",
        atrybucja="Źródło: RCB, gov.pl, opublikowano na gov.pl o godz. X",
        warunki=["Materiały urzędowe: art. 4 pkt 2 pr. aut. i ustawa o otwartych danych; wykładnia do potwierdzenia przez kancelarię.",
                 "Pełny tekst alertu i lista powiatów wolno, z linkiem i godziną publikacji na gov.pl; zdjęć i grafik nie zbierać.",
                 "Lista z ETag co 60 s; archiwum jednorazowo, 1 żądanie na 5 s (ok. 107 stron i ok. 1065 kart).",
                 "User-Agent z adresem wydawcy."],
        urls=["https://www.gov.pl/web/rcb/komunikaty", "https://www.gov.pl/web/gov/prawa-autorskie"],
        uwagi="wymaga atrybucji „Źródło: RCB, gov.pl”; limit uwzględnia archiwum (ok. 1200 żądań jednorazowo)",
    ),
    "imgw_meteo": dict(
        status=Status.DRAFT, zakres=Scope.CONTENT, endpoint=imgw_meteo.URL_METEO, wzorce=[_sciezka(imgw_meteo.URL_METEO)],
        terms_url="https://danepubliczne.imgw.pl/",
        werdykt="Publicznie tak, także Pro i API, na podstawie danych o wysokiej wartości (rozp. wyk. UE 2023/138).",
        atrybucja=f"{IMGW_ZRODLO}. Przy przetworzeniu: {IMGW_PRZETWORZENIE}.",
        warunki=["Regulamin udostępniania danych IMGW-PIB: nieodpłatnie, wymagane zdanie o źródle i informacja o przetworzeniu.",
                 "§3 ust. 2 i §5 regulaminu: użycie gospodarcze wymaga umowy, poza danymi o wysokiej wartości.",
                 "Pełny tekst regulaminu IMGW nie był czytany w Z0, tylko streszczenie: sprawdzić dosłownie przed zatwierdzeniem.",
                 "Odpowiedź bez ETag (Cache-Control: no-store); interwał 5-10 min."],
        urls=["https://danepubliczne.imgw.pl/api/data/warningsmeteo", "https://danepubliczne.imgw.pl/"],
        uwagi="wymaga dwóch zdań atrybucji IMGW; dosłowne sprawdzenie regulaminu przed zatwierdzeniem",
    ),
    "imgw_hydro": dict(
        status=Status.CONTACT_REQUIRED, zakres=Scope.CONTENT, endpoint="https://danepubliczne.imgw.pl/api/data",
        wzorce=["/api/data/warningshydro", "/api/data/hydro"], limit=0,
        terms_url="https://danepubliczne.imgw.pl/",
        werdykt="Tylko wewnętrznie; Pro i API zabronione do czasu odpowiedzi IMGW (Z0-PRAWNIK, pewność do sprawdzenia, ryzyko średnie lub wysokie).",
        atrybucja=f"{IMGW_ZRODLO}. Przy przetworzeniu: {IMGW_PRZETWORZENIE}.",
        warunki=["Nie wiadomo, czy dane hydrologiczne to dane o wysokiej wartości.",
                 "Regulamin IMGW (§3 ust. 2, §5) wymaga umowy do celów gospodarczych: zapytać IMGW.",
                 "Karta nie daje dostępu (limit dzienny 0), dopóki IMGW nie odpowie."],
        urls=["https://danepubliczne.imgw.pl/api/data/warningshydro", "https://danepubliczne.imgw.pl/api/data/hydro/"],
        uwagi="kontakt z IMGW (HVD czy umowa); limit 0 = brak dostępu",
    ),
    "gios": dict(
        status=Status.DRAFT, zakres=Scope.CONTENT, endpoint=gios.BAZA,
        wzorce=[_sciezka(gios.URL_STACJI), _sciezka(gios.URL_INDEKSU) + "/{int}"],
        # Obchód co 60 min: 1 strona listy stacji i po jednym żądaniu indeksu na stację (szacunek 350 stacji).
        zadania=1 + 350,
        terms_url="https://powietrze.gios.gov.pl/pjp/current",
        werdykt="Publicznie tak, także Pro i API (Z0-PRAWNIK, pewność prawdopodobna, ryzyko niskie).",
        atrybucja="Źródło: GIOŚ, Państwowy Monitoring Środowiska; dane nieweryfikowane na bieżąco",
        warunki=["Regulamin portalu Jakość Powietrza i strona API: wymóg czytelnego wskazania źródła.",
                 "Używać API v1; stary adres /pjp-api/rest/ nie działa poprawnie.",
                 "Dokładny adres strony z regulaminem do potwierdzenia przy zatwierdzaniu (terms_url wskazuje portal)."],
        urls=["https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll", "https://powietrze.gios.gov.pl/pjp/current"],
        uwagi="wymaga napisu „dane nieweryfikowane na bieżąco”; limit liczony z obchodu stacji (szacunek 350)",
    ),
    "firms": dict(
        status=Status.DRAFT, zakres=Scope.CONTENT, endpoint=BAZA_FIRMS,
        wzorce=[f"{SCIEZKA_FIRMS}/{{token}}/{sensor}/{OBSZAR_FIRMS}/1" for sensor in firms.SENSORY],
        terms_url="https://firms.modaps.eosdis.nasa.gov/api/",
        werdykt="Publicznie tak jako „Zgłoszone (satelita)”, także Pro i API (Z0-PRAWNIK, pewność prawdopodobna, ryzyko niskie).",
        atrybucja="NASA FIRMS (ESDIS)",
        warunki=["Wymaga bezpłatnego klucza MAP_KEY wydawcy; nie udostępniać klientom.",
                 "Limit NASA: 5000 transakcji na 10 min.",
                 "Punkty przy obiektach wojskowych i krytycznych do kolejki; nie alarmować.",
                 "Warunki atrybucji NASA do potwierdzenia."],
        urls=["https://firms.modaps.eosdis.nasa.gov/api/", "https://firms.modaps.eosdis.nasa.gov/map/"],
        uwagi="wymaga klucza w środowisku (TERAZ_FIRMS_MAP_KEY, to samo co MAP_KEY NASA); bez niego zbieracz zgłasza błąd konfiguracji",
    ),
    "emsc": dict(
        status=Status.DRAFT, zakres=Scope.CONTENT, endpoint=emsc.URL_EMSC, wzorce=[_sciezka(emsc.URL_EMSC)],
        strona="https://www.seismicportal.eu/", limit=1500,
        terms_url="https://www.seismicportal.eu/terms.html",
        werdykt="Publicznie tak, także Pro i API; warunkowo, tylko strumień WebSocket (Z0-PRAWNIK, ryzyko średnie do wyjaśnienia).",
        atrybucja="Źródło: EMSC-CSEM SeismicPortal",
        warunki=["Strumień WebSocket zamiast FDSN query: robots.txt ma Disallow dla /fdsnws/event/1/query*.",
                 "Licencja CC BY 4.0 według metadanych: potwierdzić; ewentualnie zgoda EMSC.",
                 "WebSocket nie był testowany w Z0."],
        urls=["https://www.seismicportal.eu/terms.html", emsc.URL_EMSC],
        uwagi="kanał websocket; strumień uruchamia polecenie teraz_emsc_ws; limit 1500 = zapas na ponowne połączenia",
    ),
    "usgs": dict(
        status=Status.DRAFT, zakres=Scope.CONTENT, endpoint=usgs.URL_USGS, wzorce=[_sciezka(usgs.URL_USGS)],
        terms_url="https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits",
        werdykt=f"Wskazany do karty w zleceniu jako publicznie tak; USGS nie był badany w Z0. {BRAK_OCENY}",
        atrybucja="Źródło: U.S. Geological Survey",
        warunki=["Źródło zapasowe FDSN dla Polski z planu Z2.",
                 "Przed zatwierdzeniem sprawdzić robots.txt (EMSC ma Disallow dla FDSN query) i warunki USGS.",
                 "Zakres dla Polski; interwał 5 min."],
        urls=["https://earthquake.usgs.gov/fdsnws/event/1/query"],
        uwagi="USGS bez oceny prawnej w Z0: sprawdzić robots.txt i warunki przed zatwierdzeniem",
    ),
    "gdacs": dict(
        status=Status.DRAFT, zakres=Scope.CONTENT, endpoint=gdacs.URL_GDACS, wzorce=[_sciezka(gdacs.URL_GDACS)],
        terms_url="https://www.gdacs.org/",
        werdykt="Publicznie tak; Pro i API do sprawdzenia (Z0-PRAWNIK, pewność do sprawdzenia, ryzyko niskie).",
        atrybucja="Źródło: GDACS (ONZ, JRC)",
        warunki=["RSS co 60 min; robots.txt: Request-rate 1/60 s, więc najwyżej 1 żądanie na 60 s.",
                 "Licencja do potwierdzenia (strona About zawiera zastrzeżenia JRC i UE); terms_url wskazuje stronę główną.",
                 "Redystrybucja Pro: do wyjaśnienia."],
        urls=["https://www.gdacs.org/xml/rss.xml", "https://www.gdacs.org/"],
        uwagi="jedno żądanie na 60 s; licencja i Pro do potwierdzenia",
    ),
    "cert_pl": dict(
        status=Status.DRAFT, zakres=Scope.METADATA, endpoint=cert_pl.URL_CERT, wzorce=[_sciezka(cert_pl.URL_CERT)],
        terms_url="https://cert.pl/",
        werdykt="Publicznie tak, tylko tytuł, data i link; także Pro i API (Z0-PRAWNIK, pewność prawdopodobna, ryzyko niskie).",
        atrybucja="Źródło: CERT Polska / NASK",
        warunki=["Bez treści artykułów: tylko tytuł, data, link.",
                 "Stopka „© NASK”, licencja nie wskazana: terms_url wskazuje stronę główną.",
                 "robots.txt blokuje tylko /telefon/ i /szukaj/; RSS z ETag i Last-Modified (304 potwierdzone)."],
        urls=["https://cert.pl/rss.xml"],
        uwagi="tylko tytuł, data i link (zakres metadane)",
    ),
    "pse_osp": dict(
        status=Status.DRAFT, zakres=Scope.METADATA, endpoint=pse_osp.URL_PSE, wzorce=[_sciezka(pse_osp.URL_PSE)],
        terms_url="https://www.pse.pl/komunikaty-osp",
        werdykt="Publicznie tak, tytuł, data i link; także Pro i API (Z0-PRAWNIK, pewność prawdopodobna, ryzyko niskie). Tylko Komunikaty OSP, nie API v2.",
        atrybucja="Źródło: PSE S.A.",
        warunki=["Oficjalny Atom, bez treści; komunikaty głównie rynkowe, nie awarie.",
                 "Regulaminu ani licencji nie znaleziono w Z0; brak regulaminu nie oznacza zgody.",
                 "Awarie sieci dystrybucyjnej to domena OSD, poza zakresem."],
        urls=["https://www.pse.pl/komunikaty-osp", pse_osp.URL_PSE],
        uwagi="tylko tytuł, data i link; licencji PSE nie znaleziono, zapytać PSE o warunki",
    ),
}

# Źródła z rejestru, które celowo nie dostają karty: adapter testowy.
POMINIETE = frozenset(slug for slug, klasa in ADAPTERY.items() if klasa is AdapterTestowy)


def zrodla_z_rejestru():
    return [slug for slug in ADAPTERY if slug not in POMINIETE]


def limit_dzienny(slug, zrodlo):
    """Limit dzienny żądań karty: cykle na dobę razy żądania na cykl, z zapasem; 0 dla kart bez dostępu."""
    konfiguracja = KARTY[slug]
    if "limit" in konfiguracja:
        return konfiguracja["limit"]
    zadania = konfiguracja.get("zadania", ADAPTERY[slug].limit_zadan)
    cykle = ceil(86400 / zrodlo.czestotliwosc_s)
    return ceil(cykle * zadania * ZAPAS) + konfiguracja.get("dodatek", 0)


def odstep_zadan(slug):
    """Odstęp między żądaniami do hosta: 3 s albo więcej, jeśli wymaga tego adapter albo werdykt prawny."""
    return max(3, ADAPTERY[slug].minimalny_odstep, KARTY[slug].get("odstep", 0))


def dowody(slug, zrodlo):
    konfiguracja = KARTY[slug]
    return {
        "podstawa": "Z0-PRAWNIK (17.11.2026, aktualizacja 18.11.2026) i Z0-DOSTEP (18.11.2026)",
        "werdykt": konfiguracja["werdykt"],
        "atrybucja": konfiguracja["atrybucja"],
        "warunki": konfiguracja["warunki"],
        "url": konfiguracja["urls"],
        "interwal_cyklu_s": zrodlo.czestotliwosc_s,
        "szkic": "Szkic utworzony poleceniem teraz_karty_dostepu. Zatwierdza człowiek po przeczytaniu tego pola.",
    }


class Command(BaseCommand):
    help = ("Tworzy szkice kart dostępu (status DRAFT albo CONTACT_REQUIRED) i źródła news.Source dla zbieraczy Teraz. "
            "Niczego nie zatwierdza.")

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Pokaż wynik, nic nie zapisuj.")
        parser.add_argument("--zrodlo", nargs="+", metavar="ID", help="Tylko wskazane źródła (slug z rejestru).")
        parser.add_argument("--powiaz", action="store_true",
                            help="Po zatwierdzeniu karty w panelu: włącz źródło i powiąż je ze źródłem Teraz.")

    def handle(self, *args, **opcje):
        wybrane = opcje["zrodlo"]
        dostepne = zrodla_z_rejestru()
        if wybrane:
            nieznane = sorted(set(wybrane) - set(dostepne))
            if nieznane:
                raise CommandError(f"Nieznane źródła: {', '.join(nieznane)}. Dostępne: {', '.join(dostepne)}.")
        slugi = [slug for slug in dostepne if not wybrane or slug in wybrane]
        with transaction.atomic():
            wiersze = [self.przetworz(slug, opcje["powiaz"]) for slug in slugi]
            if opcje["dry_run"]:
                transaction.set_rollback(True)
        self.wypisz(wiersze, opcje["dry_run"])
        return None

    def przetworz(self, slug, powiaz):
        zrodlo = Zrodlo.objects.select_related("zrodlo_dostepu").filter(slug=slug).first()
        konfiguracja = KARTY[slug]
        if zrodlo is None:
            return dict(slug=slug, status="brak", endpoint=konfiguracja["endpoint"], limit="-",
                        uwagi="brak wiersza źródła Teraz (migracja teraz 0004); karty nie utworzono")
        kanal = KANALY[zrodlo.sposob_dostepu]
        zrodlo_dostepu, nowe_zrodlo = self.zrodlo_dostepu(slug, zrodlo)
        karta = SourceAccessInstruction.objects.filter(source=zrodlo_dostepu).order_by("-version").first()
        nowa = karta is None
        if nowa:
            karta = SourceAccessInstruction.objects.create(
                source=zrodlo_dostepu, version=1, status=konfiguracja["status"], channel=kanal,
                allowed_scope=konfiguracja["zakres"], endpoint=konfiguracja["endpoint"],
                allowed_path_patterns=konfiguracja["wzorce"], terms_url=konfiguracja["terms_url"],
                evidence=dowody(slug, zrodlo), minimum_interval_seconds=odstep_zadan(slug),
                daily_request_cap=limit_dzienny(slug, zrodlo),
            )
        uwagi = [konfiguracja["uwagi"]]
        if not nowa:
            uwagi.append("karta już istnieje, nie zmieniono")
        if powiaz:
            uwagi.append(self.powiaz(zrodlo, zrodlo_dostepu, kanal))
        return dict(slug=slug, status=f"{karta.status}{' (nowa)' if nowa else ''}", endpoint=karta.endpoint,
                    limit=karta.daily_request_cap, uwagi="; ".join(uwagi), zrodlo_nowe=nowe_zrodlo)

    def zrodlo_dostepu(self, slug, zrodlo):
        """Źródło już powiązane zostaje; inaczej szukamy po adresie. Nowe źródło jest nieaktywnym kandydatem."""
        if zrodlo.zrodlo_dostepu_id:
            return zrodlo.zrodlo_dostepu, False
        adres = KARTY[slug].get("strona", zrodlo.adres)
        return Source.objects.get_or_create(url=adres, defaults=dict(
            name=zrodlo.nazwa, source_type=SourceType.INSTITUTION, rss_url="", is_active=False, scrape_enabled=False,
            scrape_frequency_minutes=max(1, ceil(zrodlo.czestotliwosc_s / 60)), catalog_stage="candidate",
            catalog_notes=("Teraz: źródło dla szkicu karty dostępu (teraz_karty_dostepu). "
                           "Zbieranie rusza dopiero po zatwierdzeniu karty przez człowieka."),
        ))

    def powiaz(self, zrodlo, zrodlo_dostepu, kanal):
        zatwierdzona = reviewed_instruction_for_endpoint(zrodlo_dostepu, kanal)
        if zatwierdzona is None:
            return "nie powiązano: brak zatwierdzonej, ważnej karty"
        zmiany = []
        if (not zrodlo_dostepu.is_active or not zrodlo_dostepu.scrape_enabled
                or zrodlo_dostepu.catalog_stage != "configured"):
            zrodlo_dostepu.is_active = zrodlo_dostepu.scrape_enabled = True
            zrodlo_dostepu.catalog_stage = "configured"
            zrodlo_dostepu.save(update_fields=["is_active", "scrape_enabled", "catalog_stage"])
            zmiany.append("włączono źródło")
        if zrodlo.zrodlo_dostepu_id != zrodlo_dostepu.pk:
            zrodlo.zrodlo_dostepu = zrodlo_dostepu
            zrodlo.save(update_fields=["zrodlo_dostepu"])
            zmiany.append("powiązano ze źródłem Teraz")
        return ", ".join(zmiany) or "już powiązano"

    def wypisz(self, wiersze, dry_run):
        naglowek = ("źródło", "status karty", "endpoint", "limit/dobę", "uwagi")
        tabela = [naglowek] + [(w["slug"], str(w["status"]), w["endpoint"], str(w["limit"]), w["uwagi"]) for w in wiersze]
        szerokosci = [max(len(wiersz[i]) for wiersz in tabela) for i in range(4)]
        if dry_run:
            self.stdout.write("Próba (--dry-run): nic nie zapisano.")
        for wiersz in tabela:
            self.stdout.write("  ".join(wiersz[i].ljust(szerokosci[i]) for i in range(4)) + "  " + wiersz[4])
        self.stdout.write("Karty nie są zatwierdzone. Zatwierdza człowiek w panelu administratora (karty dostępu źródeł).")
