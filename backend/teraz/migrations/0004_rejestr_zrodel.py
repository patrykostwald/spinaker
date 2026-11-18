from django.db import migrations

W = "wewnetrzny"
P = "publiczny"
OFF = "wylaczony"
IMGW = (
    "Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej - Państwowy Instytut Badawczy. "
    "Dane Instytutu Meteorologii i Gospodarki Wodnej - Państwowego Instytutu Badawczego zostały przetworzone."
)
# Stan prawny z Z0-PRAWNIK, sekcja 3 wraz z decyzją właściciela z 18.11.2026.
# Przy wyłączonych źródłach bez interwału wartość techniczna nie uruchamia zbierania.
ZRODLA = (
    ("rcb", "Alert RCB", "Rządowe Centrum Bezpieczeństwa", "rcb", "html",
     "https://www.gov.pl/web/rcb/komunikaty", 60, P, "allow",
     "Źródło: RCB, gov.pl, opublikowano na gov.pl",
     "Materiały urzędowe według zasad gov.pl i ustawy o otwartych danych. Tekst alertu i link, bez zdjęć i grafik. "
     "Lista z ETag co 60 s, archiwum jednorazowo co najmniej 5 s między żądaniami. Wykładnia do potwierdzenia przez kancelarię. Przegląd za 6 mies."),
    ("policja_rss", "Komunikaty Policji", "Policja", "policja", "rss",
     "https://www.policja.pl/dokumenty/rss/1-rss-1.rss", 600, P, "allow", "Źródło: policja.pl",
     "Publikacja po wdrożeniu i testach filtra osobowego. Pro wyłącznie tytuł, data, jednostka i link. "
     "Art. 10 RODO do potwierdzenia przez kancelarię. Przegląd za 3 mies."),
    ("policja_poszukiwani", "Poszukiwani i zaginieni", "Policja", "policja", "html",
     "https://poszukiwani.policja.gov.pl/", 86400, OFF, "deny", "",
     "Dozwolony statyczny link. Ewentualna zmiana wymaga decyzji właściciela i opinii kancelarii. Przegląd za 12 mies."),
    ("kmzb", "Krajowa Mapa Zagrożeń Bezpieczeństwa", "Komenda Główna Policji", "policja", "html",
     "https://kmzb.geoportal.gov.pl/", 86400, OFF, "deny", "",
     "Regulamin §8 pkt 2 zakazuje automatyzacji. Wymagana zgoda KGP. Przegląd po odpowiedzi."),
    ("psp", "Komunikaty PSP", "Państwowa Straż Pożarna", "psp", "html",
     "https://www.gov.pl/web/kgpsp", 600, P, "allow", "Źródło: KG PSP lub właściwa KW PSP",
     "Komunikaty urzędowe. Sprawdzić warunki KG PSP dla zestawień SWD. Przegląd za 6 mies."),
    ("sg_komunikaty", "Komunikaty Straży Granicznej", "Straż Graniczna", "sg", "html",
     "https://www.strazgraniczna.pl/pl/aktualnosci/", 1800, W, "deny", "Źródło: Straż Graniczna",
     "Użytek wewnętrzny. Klasa granica i ręczne dopuszczenie tytułu i linku. Przegląd za 6 mies."),
    ("sg_czasy", "Czas oczekiwania na granicy", "KAS, IAS Białystok", "sg", "api",
     "https://granica.gov.pl/Services/czasyService/granica.wsdl", 10800, P, "pending", "Źródło: KAS, IAS Białystok (granica.gov.pl)",
     "Dosłowne wartości z godziną stanu i atrybucją. Przesunięcie pobrania w cyklu 3 h. Warunki Pro po odpowiedzi IAS."),
    ("dorsz", "Komunikaty Dowództwa Operacyjnego RSZ", "Dowództwo Operacyjne RSZ", "wojsko", "x",
     "https://x.com/DowOperSZ", 300, W, "deny", "Źródło: Dowództwo Operacyjne RSZ, X (@DowOperSZ)",
     "Decyzja właściciela z 18.11.2026 dopuszcza wyłącznie X API wewnętrznie. Klasa wojsko, ręczne dopuszczenie, "
     "link do wpisu bez osadzania. Umowa X do sprawdzenia przez kancelarię."),
    ("mon", "Komunikaty MON", "Ministerstwo Obrony Narodowej", "wojsko", "html",
     "https://www.gov.pl/web/obrona-narodowa", 900, W, "deny", "Źródło: MON",
     "Użytek wewnętrzny. Klasa wojsko i ręczne dopuszczenie tytułu oraz linku. ETag. Przegląd za 6 mies."),
    ("gddkia_kpd", "Krajowy Punkt Dostępowy GDDKiA", "GDDKiA", "drogi", "api",
     "https://kpd.gddkia.gov.pl/", 86400, OFF, "pending", "",
     "Dostęp po rejestracji i uwierzytelnieniu certyfikatem. Interwał, atrybucja i Pro według warunków KPD. Przegląd po rejestracji."),
    ("gddkia_mapa", "Mapa GDDKiA", "GDDKiA", "drogi", "html",
     "https://drogi.gddkia.gov.pl/", 86400, OFF, "deny", "",
     "Stały zakaz automatycznego pobierania mapy. Kanał automatyczny to KPD."),
    ("plk", "Komunikaty kolejowe PKP PLK", "PKP Polskie Linie Kolejowe S.A.", "kolej", "api",
     "https://pdp-api.plk-sa.pl/", 300, P, "deny", "Źródło: PKP Polskie Linie Kolejowe S.A.",
     "Pkt 3.2 regulaminu dla bezpłatnej mapy. Pkt 3.4 zakazuje odsprzedaży. Klucz i filtr since. "
     "Archiwum i redystrybucja po pisemnej zgodzie. Monitorować zmiany regulaminu."),
    ("pansa_aup", "Plany wykorzystania przestrzeni PANSA", "Polska Agencja Żeglugi Powietrznej", "przestrzen", "html",
     "https://airspace.pansa.pl/aup/current", 1800, W, "deny", "",
     "Wewnętrznie wyłącznie pozycje cywilne, po wyjaśnieniu licencji z PANSA. Decyzja właściciela i kancelarii. Przegląd za 3 mies."),
    ("notam", "NOTAM", "Polska Agencja Żeglugi Powietrznej", "przestrzen", "api",
     "https://ais.pansa.pl/notam/", 86400, OFF, "deny", "",
     "Brak dostępu maszynowego do czasu umowy z EAD lub PANSA."),
    ("pse_api", "Dane KSE", "Polskie Sieci Elektroenergetyczne S.A.", "energetyka", "api",
     "https://api.raporty.pse.pl/api/", 300, W, "pending", "Źródło: PSE S.A.",
     "Wewnętrznie do ustalenia warunków z PSE i znaczenia pól. Infrastruktura wymaga ręcznej decyzji. Przegląd po odpowiedzi."),
    ("pse_osp", "Komunikaty OSP", "Polskie Sieci Elektroenergetyczne S.A.", "energetyka", "rss",
     "https://www.pse.pl/komunikaty-osp/-/asset_publisher/UORxdCP4f0LA/rss", 900, P, "allow", "Źródło: PSE S.A.",
     "Oficjalny Atom wyłącznie z tytułem, datą i linkiem. Przegląd za 6 mies."),
    ("imgw_meteo", "Ostrzeżenia meteorologiczne IMGW", "IMGW-PIB", "imgw_meteo", "api",
     "https://danepubliczne.imgw.pl/api/data/warningsmeteo", 600, P, "allow", IMGW,
     "Dane o wysokiej wartości według rozporządzenia wykonawczego (UE) 2023/138. "
     "Dosłownie sprawdzić regulamin IMGW. Przegląd za 6 mies."),
    ("imgw_hydro", "Ostrzeżenia hydrologiczne i stany wód IMGW", "IMGW-PIB", "imgw_hydro", "api",
     "https://danepubliczne.imgw.pl/api/data/warningshydro", 600, W, "deny", IMGW,
     "Regulamin IMGW §3 ust. 2 i §5. Status danych o wysokiej wartości lub konieczność umowy do ustalenia. Przegląd po odpowiedzi IMGW."),
    ("gios", "Indeks jakości powietrza GIOŚ", "Główny Inspektorat Ochrony Środowiska", "powietrze", "api",
     "https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll", 3600, P, "allow",
     "Źródło: GIOŚ, Państwowy Monitoring Środowiska. Dane nieweryfikowane na bieżąco.",
     "Publiczne API v1 zgodnie z regulaminem portalu Jakość Powietrza. Przegląd za 6 mies."),
    ("firms", "NASA FIRMS", "NASA", "pozary", "api",
     "https://firms.modaps.eosdis.nasa.gov/api/area/csv", 900, P, "allow", "NASA FIRMS (ESDIS)",
     "Otwarte dane i klucz wydawcy. Status Zgłoszone, satelita. Obiekty wrażliwe do kolejki. Przegląd za 6 mies."),
    ("emsc", "Strumień wstrząsów EMSC", "EMSC-CSEM", "wstrzasy", "websocket",
     "wss://www.seismicportal.eu/standing_order/websocket", 300, P, "allow", "Źródło: EMSC-CSEM SeismicPortal",
     "Oficjalny strumień WebSocket. Robots.txt wyklucza odpytywanie FDSN. Potwierdzić CC BY 4.0. Przegląd po odpowiedzi EMSC."),
    ("gdacs", "Alerty GDACS", "GDACS (ONZ i Komisja Europejska)", "katastrofy", "rss",
     "https://www.gdacs.org/xml/rss.xml", 3600, P, "pending", "Źródło: GDACS (ONZ, JRC)",
     "Oficjalny RSS co 60 min. Wymagane potwierdzenie licencji dla Pro. Przegląd za 6 mies."),
    ("cert_pl", "Komunikaty CERT Polska", "CERT Polska / NASK", "cyber", "rss",
     "https://cert.pl/rss.xml", 1800, P, "allow", "Źródło: CERT Polska / NASK",
     "Oficjalny RSS wyłącznie z tytułem, datą i linkiem. Przegląd za 6 mies."),
    ("rcb_x", "Alert RCB na X", "Rządowe Centrum Bezpieczeństwa", "rcb", "x",
     "https://x.com/RCB_RP", 300, P, "pending", "Źródło: RCB, X (@RCB_RP)",
     "Decyzja właściciela z 18.11.2026. X API, tekst i link bez osadzania. Umowa X do sprawdzenia przez kancelarię."),
    ("usgs", "Katalog wstrząsów USGS", "US Geological Survey", "wstrzasy", "api",
     "https://earthquake.usgs.gov/fdsnws/event/1/query", 300, W, "pending", "Źródło: U.S. Geological Survey",
     "Źródło zapasowe FDSN dla Polski z planu Z2. Wymagany osobny przegląd warunków i robots.txt przed otwarciem karty dostępu."),
)


def dodaj_zrodla(apps, schema_editor):
    zrodla = apps.get_model("teraz", "Zrodlo").objects.using(schema_editor.connection.alias)
    for slug, nazwa, instytucja, warstwa, kanal, adres, interwal, tryb, pro, atrybucja, podstawa in ZRODLA:
        zrodla.get_or_create(
            slug=slug,
            defaults=dict(nazwa=nazwa, instytucja=instytucja, warstwa=warstwa, sposob_dostepu=kanal,
                          adres=adres, czestotliwosc_s=interwal, tryb=OFF if tryb == OFF else W,
                          rekomendowany_tryb=tryb, redystrybucja_pro=pro, atrybucja=atrybucja,
                          podstawa_prawna=f"Z0-PRAWNIK §3. Rekomendowany tryb docelowy: {tryb}. {podstawa}"),
        )


class Migration(migrations.Migration):
    dependencies = [("teraz", "0003_warstwy_zrodla_i_wersje")]
    operations = [migrations.RunPython(dodaj_zrodla, migrations.RunPython.noop)]
