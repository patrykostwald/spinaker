"""Geokoder komunikatów: z polskiego tekstu wyciąga kody TERYT województw, powiatów i gmin.

Zasady (plan budowy Teraz, sekcje 3, 5 i 7a oraz opinia prawnika Z0):

* Wynik ma dokładność `gmina`, `powiat`, `wojewodztwo`, `kraj` albo `brak`, razem z pewnością 0..1.
* Nigdy nie zgadujemy: lepiej `brak` albo województwo niż zgadnięta gmina lub powiat. Nazwa wieloznaczna
  (np. kilka gmin „Dąbrowa”, „Czernichów”, „Słubice”) jest rozstrzygana tylko kontekstem z tekstu
  (wymienione województwo lub powiat). Bez kontekstu wynik spada do wspólnego powiatu albo województwa
  kandydatów (z niską pewnością), a gdy kandydaci leżą w różnych województwach, do `brak`.
  Jedyny wyjątek: miasto, gdy jest jedynym takim kandydatem w tym samym województwie (miasto na prawach
  powiatu obok gminy wiejskiej o tej nazwie, np. „Chełm”, albo gmina miejska obok wiejskiej w tym samym
  powiecie, np. „Mielec”), z pewnością 0,65 i uwagami `homonim`, `preferowane-miasto`
  (wyłącza to `PREFERUJ_MIASTO`). „Leszno” i „Olsztyn” mają wiejskiego homonima w innym województwie,
  więc bez kontekstu dają `brak`.
* Skrócone nazwy („w Grodzisku”, „w Ostrowie”, „w Bielsku”, „Tomaszów”) bez pełnej nazwy dają `brak`
  z uwagą `skrot`, chyba że kontekst (województwo, powiat) jednoznacznie wskazuje jedną jednostkę.
* Adresy ulic, osiedla, wsie i dzielnice (także wszystkie dzielnice Warszawy, bez względu na słowo
  „dzielnica”) nie dają gmin; PRG nie zawiera miejscowości. Rzeki (Wisła, Warta, Nysa Kłodzka...) i kluby
  („Wisła Kraków”) nie są gminami o tej nazwie.
* Wielka litera jest warunkiem nazwy gminy i miasta; przymiotniki powiatów („włodawski”) są
  rozpoznawane tylko po słowie „powiat”/„pow.” albo na liście powiatów, a województwa tylko po
  „woj./województwo” albo przed „powiaty:” / „gmina”.
* Zasięg alertu się nie zawęża: województwo i powiat wskazane wprost zostają w `teryt`, także gdy w treści
  padają dokładniejsze miejsca (te trafiają do `dopasowania`). Kod po „dla” i kod w nagłówku alertu nigdy nie
  znika. Szerszy kod znika tylko przy czystej hierarchii jednego miejsca: „w woj. X, w powiecie Y, w gminie Z”,
  dopisek za nazwą („Chełm, woj. lubelskie”, „A (woj. X)”) albo lista powiatów pod województwem bez „dla”.
* Powiat wieloznaczny („opolski”) rozstrzyga gmina tuż przed nim (dopisek) i tuż za nim („powiat opolski (gmina
  Poniatowa)”); gdy wskazują różne powiaty albo powiat zostaje nierozstrzygnięty, pewność wyniku to najwyżej 0,75.
  Dopisek województwa za nazwą („Leszno (woj. mazowieckie)”) wygrywa z powiatem z osobnego zdania alertu; konflikt
  obu obniża pewność do 0,75.
* Powiat z tekstu, który wyklucza wszystkich kandydatów nazwy („Pożar w Lesznie, powiat pruszkowski”, „Kraków,
  powiat pruszkowski”), daje sam powiat: bez gminy, bez przejścia na województwo i bez miasta spoza powiatu; gdy to
  dopisek tuż za nazwą, pewność spada do 0,6. Miasto na prawach powiatu jest zgodne z powiatem o swojej nazwie
  („Leszno”, „powiat leszczyński”: oba kody). Gminę wiejską o nazwie miasta (Tarnów, Chełm, Siedlce, Zamość...) wybiera
  tylko jawne „gmina X”; „w Tarnowie” to miasto.
* Miejsce pochodzenia („Kierowca z Lublina”, „mieszkańca Lublina”: „z/ze” + dopełniacz w zasięgu 1-2 wyrazów od
  rzeczownika osobowego albo rzeczownik i zaraz po nim dopełniacz; cała lista „z A i B”) i miejsce jednostki nie
  trafiają do `teryt`, gdy w zdaniu jest miejsce zdarzenia (jednostka: gdy jest jedyna, zostaje); zostają w
  `dopasowania` z uwagą `poza-wynikiem`. „z/ze” bez osoby, „od”, trasa i kierunek („do”, „po”, „przez”) i
  „mieszkańcy” w mianowniku (dotknięci zdarzeniem) pochodzeniem nie są. Trasą jest „do/przez/po” + nazwa wielką
  literą, zaraz za nazwą albo po słowie ruchu; „przez” z rzeczownikiem pospolitym („przez mgłę”) to przyczyna.
* Klub: samo „mecz” nie czyni nazwy klubem; potrzebne słowo klubowe (kibice, klub, drużyna, piłkarze, kolejka, liga)
  i nazwa w dopełniaczu, albo nazwa klubu z miastem klubu („Wisła Kraków”). „w Wiśle” (miejscownik) to miejsce.
* Zabezpieczenie strukturalne: wynik, w którym sporna heurystyka wycięła lub zablokowała miejsce
  (`HEURYSTYKI_WYCINAJACE`), ma pewność najwyżej `PEWNOSC_PO_WYCIECIU_MAX` (0,75) i nie wyższą niż przed wycięciem;
  wycięte miejsce zostaje w `dopasowania` z uwagą powodu. Bezsporne blokady i wycięte miejsca obecne w wyniku z innej
  wzmianki pewności nie ruszają.

Wejście to czysty tekst (HTML usuwa adapter), obcinany do `MAKS_DLUGOSC` znaków. Współrzędne: patrz `granice.py`.
"""

from __future__ import annotations

import re
from bisect import bisect_left
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from functools import lru_cache

from . import slownik as sl
from .fleksja import (
    KONCOWKI_PRZYMIOTNIKA,
    KONCOWKI_NAZW_PRZYMIOTNIKOWYCH,
    SKROTY_CZLONOW_GMIN,
    SKROTY_WOJEWODZTW,
    MapaPozycji,
    Token,
    normalizuj_wejscie,
    rdzenie_mianownika,
    tokenizuj,
    wyglada_na_wielkie_litery,
    wyrazy_nazwy,
    wyrazy_oryginalne,
    zloz_pozycyjnie,
)
from .imiona import jest_imieniem, jest_imieniem_dwuznacznym

KRAJ = "kraj"
BRAK = "brak"

# Dłuższy tekst jest obcinany (komunikat ma kilka kilobajtów); chroni przed tekstami, które liczą się długo.
MAKS_DLUGOSC = 20_000

# Miasto wygrywa z wiejskim homonimem, gdy jest jedynym takim kandydatem w tym samym województwie:
# miasto na prawach powiatu (Chełm obok gminy wiejskiej Chełm) albo gmina miejska w tym samym powiecie
# co wiejska (Mielec).
PREFERUJ_MIASTO = True

PEWNOSC_WOJ_ZNACZNIK = 0.95
PEWNOSC_WOJ_ZAKRES = 0.90
PEWNOSC_REGION = 0.75
PEWNOSC_POWIAT = 0.95
PEWNOSC_PO_KONTEKSCIE = 0.90
PEWNOSC_GMINA_ZNACZNIK = 0.90
PEWNOSC_DZIELNICA = 0.90
PEWNOSC_GMINA_SAMODZIELNA = {"grodzka": 0.90, "miejska": 0.85, "miejsko-wiejska": 0.75, "wiejska": 0.60}
PEWNOSC_MIASTO_PREFEROWANE = 0.65
PEWNOSC_SPADEK_DO_POWIATU = 0.70
PEWNOSC_SPADEK_DO_WOJEWODZTWA = 0.60
PEWNOSC_JEDNOSTKA_MAX = 0.80
PEWNOSC_SKROT_MAX = 0.75
PEWNOSC_KRAJ = 0.70
# Zabezpieczenie strukturalne: wynik, w którym heurystyka wycięła lub zablokowała miejsce (pochodzenie, jednostka, rzeka,
# klub, imię, kraina, powiat sprzeczny z nazwą), nie ma pewności wyższej niż ten próg, a więc idzie do przeglądu
# (próg automatu to 0,8). Dotyczy tylko sytuacji spornych, gdy wycięte miejsce byłoby inaczej w wyniku.
PEWNOSC_PO_WYCIECIU_MAX = 0.75
# Uwagi z powodem wycięcia w `dopasowania` (obok `poza-wynikiem`); każda to heurystyka objęta zabezpieczeniem.
HEURYSTYKI_WYCINAJACE = ("pochodzenie", "jednostka", "rzeka", "klub", "kraina", "imie", "powiat-wyklucza")
PEWNOSC_SPRZECZNY_KONTEKST = 0.60  # powiat z tekstu wyklucza nazwę: zostaje sam powiat, ale z niską pewnością
WSPOLCZYNNIK_WIELKICH_LITER = 0.85
WSPOLCZYNNIK_ODRZUCONEJ_NAZWY = 0.90

# Miasta na prawach powiatu i powiaty ziemskie, które noszą ich nazwę („Leszno” - „leszczyński”, „Kalisz” - „kaliski”).
# Miasto i taki powiat są w tekście zgodne, choć kod miasta nie leży w kodzie powiatu. Pary wyznaczono na danych
# (nazwa powiatu wspólna z nazwą miasta, w tym samym województwie); test `test_pary_miast_i_powiatow_sa_w_danych`
# sprawdza, że każda para istnieje w `teryt.json`. Szczecin (powiat policki), Warszawa i miasta śląskie bez powiatu
# o swojej nazwie nie mają pary.
_POWIAT_O_NAZWIE_MIASTA = {
    "Legnica": "legnicki", "Wrocław": "wrocławski", "Wałbrzych": "wałbrzyski", "Bydgoszcz": "bydgoski",
    "Grudziądz": "grudziądzki", "Toruń": "toruński", "Włocławek": "włocławski", "Biała Podlaska": "bialski",
    "Chełm": "chełmski", "Lublin": "lubelski", "Zamość": "zamojski", "Gorzów Wielkopolski": "gorzowski",
    "Zielona Góra": "zielonogórski", "Łódź": "łódzki wschodni", "Piotrków Trybunalski": "piotrkowski",
    "Skierniewice": "skierniewicki", "Kraków": "krakowski", "Nowy Sącz": "nowosądecki", "Tarnów": "tarnowski",
    "Ostrołęka": "ostrołęcki", "Płock": "płocki", "Radom": "radomski", "Siedlce": "siedlecki", "Opole": "opolski",
    "Krosno": "krośnieński", "Przemyśl": "przemyski", "Rzeszów": "rzeszowski", "Tarnobrzeg": "tarnobrzeski",
    "Białystok": "białostocki", "Łomża": "łomżyński", "Suwałki": "suwalski", "Gdańsk": "gdański", "Słupsk": "słupski",
    "Bielsko-Biała": "bielski", "Częstochowa": "częstochowski", "Gliwice": "gliwicki", "Rybnik": "rybnicki",
    "Kielce": "kielecki", "Elbląg": "elbląski", "Olsztyn": "olsztyński", "Kalisz": "kaliski", "Konin": "koniński",
    "Leszno": "leszczyński", "Poznań": "poznański", "Koszalin": "koszaliński",
}

_WOJ = frozenset({"woj", "wojew"})
_POW = frozenset({"powiat", "powiatu", "powiatem", "powiaty", "powiatow", "powiatach", "powiatom", "powiatami", "powiecie", "pow"})
_GM = frozenset({"gmina", "gminy", "gminie", "gmine", "gmin", "gminach", "gminom", "gminami", "gm"})
_MIASTO = frozenset({"miasto", "miasta", "miastu", "miastem", "miescie", "m"})
_WIES = frozenset({"miejscowosc", "miejscowosci", "miejscowoscia", "wies", "wsi", "wsie", "wsiach", "osiedle", "osiedlu", "osiedla", "solectwo", "solectwie"})
_ULICA = frozenset({"ul", "ulica", "ulicy", "ulice", "ulicach", "al", "aleja", "alei", "aleje", "pl", "plac", "placu", "os", "rondo", "ronda"})
_DZIELNICA = frozenset({"dzielnica", "dzielnicy", "dzielnicie", "dzielnice", "dzielnic", "dzielnicach"})
_SKROTY_Z_KROPKA = frozenset({"gm", "m", "pl", "al", "os"})
_MODYFIKATORY_GMINY = frozenset({"miejska", "miejskiej", "wiejska", "wiejskiej", "miejsko", "wiejsko"})
_LACZNIKI = frozenset({"i", "oraz", "lub", "albo"})

_DZIELNICE_WARSZAWY = (
    "Bemowo", "Białołęka", "Bielany", "Mokotów", "Ochota", "Praga-Południe", "Praga-Północ", "Rembertów",
    "Targówek", "Ursus", "Ursynów", "Wawer", "Wesoła", "Wilanów", "Włochy", "Wola", "Śródmieście", "Żoliborz",
)
KOD_WARSZAWY = "1465011"

# Nieregularne odmiany nazw (rdzeń mianownika nie wystarcza); klucz: nazwa gminy w słowniku.
_NIEREGULARNE = {
    "Białystok": ("Białegostoku", "Białymstoku", "Białemustoku"),
    "Krasnystaw": ("Krasnegostawu", "Krasnymstawie", "Krasnemustawowi", "Krasnymstawem"),
}

# Nazwy regionów równoważne województwu (tylko te jednoznaczne).
_REGIONY = {
    "Mazowsze": "14", "Małopolska": "12", "Wielkopolska": "30", "Podkarpacie": "18",
    "Podlasie": "20", "Lubelszczyzna": "06",
}

# Nazwy gmin, które są też zwykłymi słowami. „Tylko znacznik”: wymagają słowa „gmina/miasto/powiat”
# (np. „Nowy Jork” nie jest gminą Nowe). „Nie na początku zdania”: wystarczy wielka litera w środku zdania.
_TYLKO_ZNACZNIK = frozenset({"nowe", "nowa", "dobra", "dobre", "czarna", "czarne", "biala", "stare"})
_NIE_NA_POCZATKU_ZDANIA = frozenset({"kolo", "kowal", "gniew", "pila", "marki", "klucze", "ploty", "mikolajki", "kozy", "brody", "kamien", "pokoj"})
# Pierwsze wyrazy wielu nazw („Nowy Sącz”, „Stary Sącz”, „Wielka Wieś”): samo takie słowo nie jest skrótem miejsca.
_GENERYCZNE_PIERWSZE = frozenset({
    "nowy", "nowa", "nowe", "stary", "stara", "stare", "wielki", "wielka", "wielkie", "maly", "mala", "male",
    "duzy", "duza", "duze", "dolny", "dolna", "dolne", "gorny", "gorna", "gorne", "czarny", "czarna", "czarne",
    "bialy", "biala", "biale", "zielony", "zielona", "zielone", "swiety", "swieta", "swiete", "kolo", "dobre", "dobra",
})

# Rzeki, które są też nazwami gmin (Wisła, Warta, Nysa, Pilica, Wieprz, Narew, Słupia, Łeba, Oława...) oraz
# większe rzeki bez gminy o tej nazwie (dla porządku listy). Nazwy bez polskich znaków, mianownik.
_RZEKI = frozenset((n,) for n in (
    "wisla", "odra", "warta", "bug", "narew", "san", "pilica", "wieprz", "nysa", "bobr", "dunajec", "notec",
    "wda", "brda", "dreweca", "prosna", "bzura", "ner", "kamienna", "radomka", "biebrza", "sola", "skawa", "raba",
    "wisloka", "wislok", "poprad", "nida", "liwiec", "wkra", "rega", "parseta", "slupia", "lyna", "pasleka", "obra",
    "gwda", "drawa", "ropa", "olza", "kaczawa", "bystrzyca", "widawa", "tanew", "huczwa", "swider", "wiar", "orla",
    "barycz", "sleza", "olawa", "leba", "suprasl", "narewka", "wilga", "gac",
))
# Pierwsze wyrazy nazw klubów sportowych („Wisła Kraków”, „Legia Warszawa”, „Raków Częstochowa”), w mianowniku.
# Nazwa klubu (w każdym przypadku) blokuje też miasto stojące tuż po niej: to nazwa drużyny, nie miejsce zdarzenia.
_KLUBY = (
    "Legia", "Lech", "Śląsk", "Pogoń", "Jagiellonia", "Górnik", "Korona", "Zagłębie", "Wisła", "Odra", "Raków",
    "Cracovia", "Arka", "Lechia", "Widzew", "ŁKS", "Stal", "Motor", "Warta", "Piast", "Ruch", "Polonia",
    "Resovia", "GKS", "Puszcza", "Stomil", "Znicz",
)
# Słowa z kręgu sportu w zdaniu: nazwa klubu bez miasta za nią nie jest wtedy gminą („Kibice Wisły zatrzymani w Płocku”).
_SPORT_PREFIKSY = ("kibic", "klub", "pilkar", "zawodnik", "trener", "druzyn", "stadion", "derb", "puchar", "kolejk", "kolejc")
# Samo „mecz/mecze” to kontekst słaby: nie czyni nazwy klubem (zob. `_blokada_klubu`); „meczet” to nie mecz.
_SPORT_SLABY_PREFIKSY = ("mecz",)
_SPORT_NIE = ("meczet",)
# Przyimki z miejscownikiem: „w Wiśle”, „na Odrze” to miejsce, a nie nazwa klubu w dopełniaczu („Kibice Wisły”).
_PRZYIMKI_MIEJSCOWNIKA = frozenset({"w", "we", "na", "przy"})
_SPORT_WYRAZY = frozenset({"liga", "ligi", "lidze", "lige", "ligach", "ligom", "ligami", "lig"})  # „lig...” w prefiksie łapałoby „ligawa”
_OKNO_SPORTU = 40
_PRZED_RZEKA = frozenset({"na", "nad", "wzdluz", "rzeka", "rzeki", "rzece", "rzeke", "rzekach", "dorzecze", "dorzeczu", "dolinie"})
# Słowa hydrologiczne w zasięgu dwóch wyrazów przed nazwą rzeki („Poziom Wisły”, „stan wód Wisły”, „wylew Warty”,
# „na brzegu Odry”, „fala kulminacyjna Bugu”): nazwa jest wtedy rzeką, także bez słów o stanie wód w całym tekście.
# „woda/wody” tu nie ma: „Przerwa w dostawie wody w Wiśle” i „Brak wody w Oławie” mówią o wodociągu, nie o rzece.
_HYDRO_PRZED_RZEKA = frozenset({
    "poziom", "poziomu", "poziomie", "poziomem", "poziomy", "stan", "stanu", "stanie", "stanem", "stany",
    "rzeka", "rzeki", "rzece", "rzeke", "nad", "na",
    "brzeg", "brzegu", "brzegi", "brzegach", "brzegow", "wylew", "wylewu", "wylewie", "wylewem", "wylewy",
    "fala", "fali", "fale", "fala", "przekroczenie", "przekroczeniu", "przekroczenia", "przekroczyl", "przekroczyla",
    "przekroczylo", "wezbranie", "wezbrania", "wezbraniu", "przybor", "przyboru", "przyborze", "kulminacja", "kulminacji",
    "korycie", "koryto", "koryta", "nurt", "nurcie", "nurtu",
})
# „św. Anny Lubartów”, „ul. Anny Jantar Opole”, „im. Jana Kalisz”: imię po tych wyrazach to patron, a nie osoba z nazwiskiem.
_PRZED_PATRONEM = frozenset({"sw", "ul", "al", "im", "ulica", "ulicy", "aleja", "alei", "plac", "placu", "os", "rondo", "ronda"})
_DRUGI_CZLON_RZEKI = ("klodzk", "luzyck")  # „Nysa Kłodzka”, „Nysa Łużycka”

_PRZYIMKI_MIEJSCA = frozenset({"w", "we", "z", "ze", "do", "od", "na", "nad", "pod", "przy", "kolo", "k", "po", "za", "obok"})
_JEDNOSTKA_PREFIKSY = ("komend", "komisariat", "prokuratur", "urzad", "posterunek", "jednostk")
_JEDNOSTKA_WYRAZY = frozenset({"sad", "sadu", "sadzie", "sadem"})
# Skróty jednostek służb (Policja, PSP): KPP, KMP, KWP, KSP, KP, JRG, PSP (w tym KP PSP, KW PSP, KM PSP).
_JEDNOSTKA_SKROTY = frozenset({"kpp", "kmp", "kwp", "ksp", "kp", "jrg", "psp", "km"})
# Małą literą dopuszczamy w nazwie jednostki tylko te wyrazy (reszta małych liter przerywa przeszukiwanie wstecz).
_JEDNOSTKA_PRZEDROSTKI_MALE = ("wojewodzk", "powiatow", "rejonow", "miejsk", "stoleczn", "okregow")
_JEDNOSTKA_SLOWA_MALE = frozenset({"policji", "policja", "straz", "strazy", "pozarnej", "granicznej", "ratowniczo", "gasnicza", "gasniczej", "gasnicze", "panstwowej"})
_POW_MNOGA = frozenset({"powiaty", "powiatow", "powiatach", "powiatom", "powiatami"})
# Wyrazy, które w tekście bywają odmianą nazwy gminy, a nią nie są („W Polsce obowiązują ostrzeżenia” to nie „Polska Cerekiew”).
_NIE_NAZWY_GMIN = frozenset({"polska", "polsce", "polske", "polski", "polsko"})
_SEP_PROSTY = re.compile(r"[ \t\u00a0\-]+")
_SEP_PIERWSZEGO = re.compile(r"[\s:\-\u2013\u2014(.]{0,6}")
_SEP_ZAKRESU = re.compile(r"[\s\-\u2013\u2014:,(]{0,4}")
_KONIEC_ZDANIA = ".!?;\n"
# Miejsce pochodzenia (wyrazy złożone: małe litery bez polskich znaków, pełne formy, a nie prefiksy: „turystyczny” to
# nie „turysta”). `_OSOBA_Z`: rzeczownik osobowy, po którym „z/ze + dopełniacz” w zasięgu 1-2 wyrazów wskazuje, skąd
# ktoś pochodzi („Kierowca z Lublina”, „Strażacy z Lublina”, „Kierowca ciężarówki z Lublina”). `_OSOBA_BEZPOSREDNIO`:
# rzeczownik, po którym sam dopełniacz wskazuje pochodzenie („mieszkańca Lublina”, „kierowca Lublina”). Mianownik
# liczby mnogiej „mieszkańcy” oznacza dotkniętych zdarzeniem („Mieszkańcy Lublina bez prądu”), więc nie wchodzi.
_NARZEDNIK = ("em", "ą", "ami", "ymi", "imi")  # końcówki narzędnika: „z Tuchowem”, „z Warszawą”
_OSOBA_BEZPOSREDNIO_WZORZEC = (
    r"mieszkan(?:iec|ca|cowi|cem|cu|cy|cow|com|cami|cach|ka|ki|ce|ke|ek|kom|kami|kach)"
    r"|kierowc(?:a|y|e|ow|om|ami|ach)"
    r"|obywatel(?:e|i|a|owi|em|u|om|ami|ach|ka|ki|ce|ke|ek|kom|kami|kach)?"
    r"|rodak(?:a|i|ow|owi|iem|u|om|ami|ach)?|rodacy"
    r"|rodacz(?:ka|ki|ke|ce|ek|kom|kami|kach)"
    r"|pochodz(?!eni)\w*"
)
_OSOBA_BEZPOSREDNIO = re.compile(_OSOBA_BEZPOSREDNIO_WZORZEC)
_OSOBA_Z = re.compile(
    _OSOBA_BEZPOSREDNIO_WZORZEC
    + r"|turyst(?:a|y|e|o|ow|om|ami|ach|ka|ki|ke|ce|ek|kom|kami|kach)|turysci"
    r"|strazac(?:y|a|owi|em|u|ow|om|ami|ach)|strazak(?:a|owi|iem|u)?"
    r"|policjan(?:t|ta|ci|towi|tem|cie|tow|tom|tami|tach|tka|tki|tke|tce|tek|tkom|tkami|tkach)"
    r"|pogotowi(?:e|a|u|em)"
    r"|mezczyzn(?:a|y|e|ie|o|om|ami|ach)?|mezczyzni"
    r"|kobiet(?:a|y|e|ie|o|om|ami|ach)?"
)
_NIE_POCHODZENIE_MIANOWNIK = frozenset({"mieszkancy"})
_SLOWA_TRASY = frozenset({"do", "po", "przez"})  # trasa i kierunek („z A przez B do C”, „od A po B”): nie wycina miejsc
# Słowa ruchu przed „do/przez/po”: bez nich (i bez przylegania do nazwy) „przez” to przyczyna, a nie trasa.
_RUCH_PREFIKSY = ("jech", "jadac", "jadacy", "jedzie", "podroz", "zmierza", "wracal", "przejezdz", "kierowal")
_RUCH_WYRAZY = frozenset({"trasa", "trasie", "trase", "trasy", "droga", "drodze", "droge"})
_OKNO_TRASY = 5  # tyle wyrazów za nazwą (lub końcem listy) sprawdzamy w poszukiwaniu słowa trasy
_KONIEC_OKNA_TRASY = frozenset({"i", "oraz"})  # spójnik zamyka okno: „jechał do Warszawy i miał wypadek w Płocku”
_MAKS_ELEMENTOW_LISTY = 8

# Zasięg krajowy: tylko przy słowach o zasięgu („obowiązuje w całym kraju”, „na terenie całego kraju”,
# „dla całej Polski”). „z całej Polski” czy „najwięcej w całym kraju” zasięgiem nie są.
_FRAZA_KRAJU = r"(?:w\s+calej\s+polsce|w\s+calym\s+kraju|calej\s+polski|calego\s+kraju)"
_CZASOWNIK_ZASIEGU = r"(?:obowiazuj\w*|dotyczy\w*|dotycz\w*|ogloszon\w*|ogloszono|wprowadzon\w*|wprowadzono|wysla\w*|wyslan\w*|zasieg\w*)"
_WZORCE_KRAJU = tuple(re.compile(w) for w in (
    r"\bdla\s+(calej\s+polski|calego\s+kraju)\b",
    r"\bdla\s+\w+\s+(w\s+calej\s+polsce|w\s+calym\s+kraju)\b",
    r"\bna\s+(?:terenie|obszarze)\s+(calego\s+kraju|calej\s+polski)\b",
    rf"\b{_CZASOWNIK_ZASIEGU}\b[^.!?\n]{{0,40}}?\b({_FRAZA_KRAJU})\b",
    rf"\b({_FRAZA_KRAJU})\b[^.!?\n]{{0,40}}?\b{_CZASOWNIK_ZASIEGU}\b",
))
# „z całej Polski”, „od całego kraju”: skąd pochodzą ludzie lub rzeczy, a nie zasięg ostrzeżenia.
_PRZYIMEK_POCHODZENIA = re.compile(r"\b(?:z|ze|od)\s+$")
# „Najwięcej … w całym kraju”: statystyka, a nie zasięg ostrzeżenia.
_ILOSC_W_ZDANIU = re.compile(r"\b(?:najwiec\w*|najmniej\w*|najczesc\w*|najlicz\w*)\b")
# Komunikaty hydrologiczne: nazwa rzeki, która jest też gminą, nie jest wtedy miejscem.
_HYDROLOGIA = re.compile(
    r"hydrolog|wezbran|powodz|wylew|przybor|kulminac|\bstan\w*\s+(?:alarmow|ostrzegawcz|wod)|\bpoziom\w*\s+wod"
    r"|\brzek|\brzece|\bkorytem?\b|\bprzeplyw")


# --------------------------------------------------------------------------- wynik

@dataclass(frozen=True, slots=True)
class Dopasowanie:
    """Jedno rozpoznane miejsce w tekście."""

    fraza: str  # fragment tekstu
    start: int  # pozycje znaków w tekście wejściowym
    koniec: int
    rodzaj: str  # wojewodztwo | powiat | gmina | kraj
    tryb: str  # znacznik | lista | zakres | samodzielne | dzielnica | region | kraj
    teryt: tuple[str, ...]  # przyjęte kody (puste: nie udało się rozstrzygnąć)
    dokladnosc: str  # gmina | powiat | wojewodztwo | kraj | brak
    pewnosc: float
    kandydaci: tuple[str, ...] = ()  # wszystkie kody o tej nazwie, gdy jest wieloznaczna
    uwagi: tuple[str, ...] = ()  # homonim, kontekst, jednostka, skrot, spadek-do-powiatu, spadek-do-wojewodztwa...

    def jako_dict(self) -> dict:
        return {
            "fraza": self.fraza, "start": self.start, "koniec": self.koniec, "rodzaj": self.rodzaj,
            "tryb": self.tryb, "teryt": list(self.teryt), "dokladnosc": self.dokladnosc,
            "pewnosc": self.pewnosc, "kandydaci": list(self.kandydaci), "uwagi": list(self.uwagi),
        }


@dataclass(frozen=True, slots=True)
class Wynik:
    teryt: tuple[str, ...]  # posortowane, bez powtórzeń; zob. zasady zasięgu w opisie modułu
    dokladnosc: str  # gmina | powiat | wojewodztwo | kraj | brak (najgrubsza z przyjętych)
    pewnosc: float  # 0..1; dla `brak` 0.0
    dopasowania: tuple[Dopasowanie, ...] = ()
    uwagi: tuple[str, ...] = ()  # np. „obcieto-tekst”, gdy wejście przekroczyło `MAKS_DLUGOSC`

    def jako_dict(self) -> dict:
        return {
            "teryt": list(self.teryt), "dokladnosc": self.dokladnosc, "pewnosc": self.pewnosc,
            "dopasowania": [d.jako_dict() for d in self.dopasowania], "uwagi": list(self.uwagi),
        }


# --------------------------------------------------------------------------- indeksy nazw

@dataclass(slots=True)
class _Grupa:
    wyrazy: tuple[str, ...]  # złożone wyrazy mianownika
    rdzenie: tuple[dict[str, frozenset[str] | None], ...]
    wielka: bool  # nazwa wymaga wielkiej litery w tekście
    skroty: dict[str, str]  # skróty członów z kropką („Wlkp.”) -> rdzeń członu
    kody: list[str] = field(default_factory=list)
    oryginaly: list[tuple[str, ...]] = field(default_factory=list)  # wyrazy nazwy z polskimi znakami (warianty)


class _Indeks:
    """Nazwy jednostek po pierwszym wyrazie. `mnoga`: jednowyrazowa nazwa na „-y/-i” to liczba mnoga („Zawady”)."""

    def __init__(self, wielka: bool, mnoga: bool = False, skroty: dict[str, str] | None = None):
        self.wielka_domyslnie = wielka
        self.mnoga = mnoga
        self.skroty = skroty or {}
        self.grupy: dict[tuple, _Grupa] = {}
        self.po_pierwszym: dict[str, list[_Grupa]] = defaultdict(list)

    def dodaj(self, nazwa: str, kod: str, wielka: bool | None = None) -> None:
        wyrazy = tuple(wyrazy_nazwy(nazwa))
        wielka = self.wielka_domyslnie if wielka is None else wielka
        klucz = (wyrazy, wielka)
        grupa = self.grupy.get(klucz)
        if grupa is None:
            mnoga = self.mnoga and len(wyrazy) == 1 and wyrazy[0].endswith(("y", "i"))
            grupa = _Grupa(wyrazy, tuple(rdzenie_mianownika(w, mnoga) for w in wyrazy), wielka, self.skroty)
            self.grupy[klucz] = grupa
            for rdzen in grupa.rdzenie[0]:
                self.po_pierwszym[rdzen].append(grupa)
        oryginal = wyrazy_oryginalne(nazwa)
        if oryginal not in grupa.oryginaly:
            grupa.oryginaly.append(oryginal)
        if kod not in grupa.kody:
            grupa.kody.append(kod)


@dataclass(slots=True)
class _Indeksy:
    gminy: _Indeks
    powiaty: _Indeks
    wojewodztwa: _Indeks
    regiony: _Indeks
    dzielnice: _Indeks
    kluby: _Indeks


@lru_cache(maxsize=1)
def _indeksy() -> _Indeksy:
    s = sl.slownik()
    gminy = _Indeks(True, mnoga=True, skroty=SKROTY_CZLONOW_GMIN)
    powiaty, woj = _Indeks(False), _Indeks(False, skroty=SKROTY_WOJEWODZTW)
    regiony, dzielnice = _Indeks(True), _Indeks(True, mnoga=True)
    for j in s.gminy:
        gminy.dodaj(j.nazwa, j.kod)
        for forma in _NIEREGULARNE.get(j.nazwa, ()):
            gminy.dodaj(forma, j.kod)
    for j in s.powiaty:
        powiaty.dodaj(j.nazwa, j.kod, wielka=j.rodzaj == "grodzki")
    for j in s.wojewodztwa:
        woj.dodaj(j.nazwa, j.kod)
    for nazwa, kod in _REGIONY.items():
        regiony.dodaj(nazwa, kod)
    for nazwa in _DZIELNICE_WARSZAWY:
        dzielnice.dodaj(nazwa, KOD_WARSZAWY)
    kluby = _Indeks(True)
    for nazwa in _KLUBY:
        kluby.dodaj(nazwa, "klub")
    return _Indeksy(gminy, powiaty, woj, regiony, dzielnice, kluby)


def _zgodny_rdzen(token: Token, rdzenie: dict[str, frozenset[str] | None], mianownik: str, skroty: dict[str, str]) -> bool:
    if token.z_kropka and skroty.get(token.zlozony) in rdzenie:  # „Wlkp.”, „Maz.”, „woj. małop.”
        return True
    for rdzen, koncowka in token.kandydaci().items():
        if rdzen in rdzenie:
            dozwolone = rdzenie[rdzen]
            if dozwolone is not None and koncowka not in dozwolone:
                continue
            # „gdańskiego” to przymiotnik, a nie forma miasta Gdańsk (nazwa na spółgłoskę lub „o”)
            if koncowka in KONCOWKI_PRZYMIOTNIKA and mianownik[-1] not in KONCOWKI_NAZW_PRZYMIOTNIKOWYCH:
                continue
            # „Główny”, „Główne” to nie forma miasta Głowno: nazwa na „-o” nie ma rzeczownikowych form na „-y” i „-e”
            if koncowka in ("y", "e") and mianownik.endswith("o"):
                continue
            return True
    return False


def _o_kreskowane_w_tekscie(wyraz: str, warianty: list[tuple[str, ...]], k: int) -> bool:
    """Czy „ó” w wyrazie z tekstu stoi tam, gdzie każdy wariant nazwy ma zwykłe „o” („Główna” a nazwa „Głowno”).

    „ó” i „o” składają się do tego samego znaku, więc przymiotnik „Główna” wyglądałby jak dopełniacz „Głowna”.
    Dotyczy nazw rzeczownikowych na „-o” (odmiana nie zmienia „o” w „ó”); „ó” w takim miejscu to inny wyraz.
    W nazwach w liczbie mnogiej „o” zmienia się w „ó” w dopełniaczu („z Kóz”, „Brodów”), więc tam reguła nie działa.
    """
    male = wyraz.lower()
    for idx, znak in enumerate(male):
        if znak == "ó" and all(idx < len(w[k]) and w[k][idx] == "o" for w in warianty):
            return True
    return False


def _zgodna(tokeny: list[Token], i: int, grupa: _Grupa, ile: int) -> bool:
    """Czy pierwsze `ile` wyrazów nazwy pasuje do tokenów od `i`."""
    for k in range(ile):
        tk = tokeny[i + k]
        if grupa.wielka and not tk.wielka:
            return False
        if k and not (tk.sep and _SEP_PROSTY.fullmatch(tk.sep)):
            return False
        if not _zgodny_rdzen(tk, grupa.rdzenie[k], grupa.wyrazy[k], grupa.skroty):
            return False
        if grupa.wyrazy[k].endswith("o") and ("ó" in tk.tekst or "Ó" in tk.tekst) and _o_kreskowane_w_tekscie(tk.tekst, grupa.oryginaly, k):
            return False
    return True


def _grupy_od(tokeny: list[Token], i: int, indeks: _Indeks) -> list[_Grupa]:
    t = tokeny[i]
    if t.cyfra:
        return []
    kandydaci: dict[int, _Grupa] = {}
    for rdzen in t.kandydaci():
        for grupa in indeks.po_pierwszym.get(rdzen, ()):
            kandydaci[id(grupa)] = grupa
    skrot = indeks.skroty.get(t.zlozony) if t.z_kropka else None  # „woj. małop.”: pierwszy człon jest skrótem
    if skrot:
        for grupa in indeks.po_pierwszym.get(skrot, ()):
            kandydaci[id(grupa)] = grupa
    return list(kandydaci.values())


def _szukaj(tokeny: list[Token], i: int, indeks: _Indeks) -> tuple[int, list[_Grupa]] | None:
    """Najdłuższe dopasowanie nazwy z indeksu od tokenu `i`: (liczba tokenów, grupy o tej długości)."""
    najdluzsza, grupy = 0, []
    for grupa in _grupy_od(tokeny, i, indeks):
        dlugosc = len(grupa.wyrazy)
        if dlugosc < najdluzsza or i + dlugosc > len(tokeny):
            continue
        if not _zgodna(tokeny, i, grupa, dlugosc):
            continue
        if dlugosc > najdluzsza:
            najdluzsza, grupy = dlugosc, []
        grupy.append(grupa)
    return (najdluzsza, grupy) if grupy else None


def _skrocone(tokeny: list[Token], i: int, indeks: _Indeks, ile: int) -> list[_Grupa]:
    """Dłuższe nazwy, których pierwsze `ile` wyrazów pasuje do tokenów od `i` („Grodzisk” - „Grodzisk Mazowiecki”)."""
    if i + ile > len(tokeny):
        return []
    return [g for g in _grupy_od(tokeny, i, indeks) if len(g.wyrazy) > ile and _zgodna(tokeny, i, g, ile)]


def _kody(grupy: list[_Grupa]) -> list[str]:
    wynik: list[str] = []
    for grupa in grupy:
        for kod in grupa.kody:
            if kod not in wynik:
                wynik.append(kod)
    return wynik


# --------------------------------------------------------------------------- znaczniki

def _znacznik(tokeny: list[Token], i: int) -> str | None:
    t = tokeny[i]
    z = t.zlozony
    if z in _SKROTY_Z_KROPKA and (not t.z_kropka or t.sep.endswith((".", "/"))):
        return None
    if z in _WOJ or z.startswith("wojewodztw"):
        return "woj"
    if z in _POW:
        return "pow"
    if z in _GM:
        return "gm"
    if z in _MIASTO:
        return "miasto"
    if z in _WIES:
        return "wies"
    if z in _ULICA:
        return "ulica"
    if z in _DZIELNICA:
        return "dzielnica"
    return None


def _pomin_nazwe(tokeny: list[Token], j: int, maks: int) -> int:
    """Koniec nazwy własnej (ulicy, wsi) zaczynającej się w `j`: kolejne wyrazy wielkie lub liczby."""
    k = j
    while k < len(tokeny) and k - j < maks:
        t = tokeny[k]
        if k > j and any(c in t.sep for c in ".,;:!?\n"):
            break
        if not (t.wielka or t.cyfra):
            break
        k += 1
    return k


# --------------------------------------------------------------------------- trafienia

@dataclass(slots=True)
class _Trafienie:
    start: int  # indeksy tokenów [start, koniec)
    koniec: int
    typ: str  # woj | pow | gmina | region
    tryb: str  # znacznik | lista | zakres | samodzielne | dzielnica | region
    kody: list[str]
    znacznik: str = ""  # gm | miasto (dla gmin)
    lancuch: int = 0
    lancuch_koniec: int = 0
    zakres: set[str] = field(default_factory=set)  # województwa z zakresu (dla powiatów)
    kontekst_wielkich: bool = False  # tekst WIELKIMI LITERAMI: samodzielne trafienie słabsze
    bez_przyimka: bool = False  # nazwa bez przyimka miejsca: tylko miasto (nie wieś ani miasteczko)
    skrot: bool = False  # skrócona nazwa: wymaga kontekstu
    poczatek: int = -1  # indeks tokenu znacznika („woj.”, „powiat”, „gmina”) albo początku nazwy bez znacznika
    zakres_doprecyzowuje: bool = False  # zakres województwa jest nagłówkiem listy lub dopiskiem „A (woj. X)”, nie osobnym zasięgiem
    zakres_z_naglowka: bool = False  # województwo stoi przed listą powiatów jako jej nagłówek (a nie jako dopisek za nazwą)
    blokada: str = ""  # powód zablokowania nazwy („rzeka”, „klub”, „kraina”): trafienie idzie do listy blokad, a nie do wyniku
    po_imieniu: bool = False  # nazwa stoi po imieniu, które samo bywa nazwą gminy („Hanna Kraków”): odpada, gdy jest miejsce z przyimkiem


@dataclass(slots=True)
class _Pozycja:
    """Jedna nazwa z listy po znaczniku: tokeny [start, koniec) i kody; `woj` to województwo w nawiasie za nazwą."""

    start: int
    koniec: int
    kody: list[str]
    woj: tuple[int, int, list[str]] | None = None  # (indeks znacznika „woj.”, koniec nazwy, kody), tokeny po nawiasie „(”


def _woj_w_nawiasie(tokeny: list[Token], p: int) -> tuple[int, int, list[str]] | None:
    """„(woj. małopolskie)” tuż za nazwą: zwraca (indeks znacznika, koniec nazwy województwa, kody) albo None.

    Tokeny od `p`: znacznik „woj.” po nawiasie otwierającym, nazwa województwa, a za nią nawias zamykający.
    """
    n = len(tokeny)
    if p + 1 >= n or "(" not in tokeny[p].sep or _znacznik(tokeny, p) != "woj":
        return None
    if tokeny[p].sep.strip() != "(" or not _SEP_PIERWSZEGO.fullmatch(tokeny[p + 1].sep):
        return None
    znaleziono = _szukaj(tokeny, p + 1, _indeksy().wojewodztwa)
    if not znaleziono:
        return None
    koniec = p + 1 + znaleziono[0]
    if koniec >= n or not tokeny[koniec].sep.lstrip().startswith(")"):
        return None
    return p, koniec, _kody(znaleziono[1])


def _wczytaj_lancuch(tokeny: list[Token], p: int, indeks: _Indeks, powiaty: bool = False) -> list[_Pozycja]:
    """Lista nazw po znaczniku: „A, B i C”. Zwraca pozycje w tokenach.

    `powiaty`: lista powiatów może mieć za nazwą województwo w nawiasie („A (woj. X), B (woj. Y)”). Taki nawias
    w środku listy nie przerywa jej; za ostatnią nazwą zostaje nietknięty (obsłuży go zwykłe rozpoznanie województwa).
    Pozycje listy powiatów mogą też stać rozdzielone średnikiem („powiaty: A; B; C”).
    """
    pozycje: list[_Pozycja] = []
    n = len(tokeny)
    if p >= n or not _SEP_PIERWSZEGO.fullmatch(tokeny[p].sep):
        return pozycje
    while p < n:
        znaleziono = _szukaj(tokeny, p, indeks)
        if not znaleziono:
            break
        dlugosc, grupy = znaleziono
        pozycje.append(_Pozycja(p, p + dlugosc, _kody(grupy)))
        p += dlugosc
        if p >= n:
            break
        woj = _woj_w_nawiasie(tokeny, p) if powiaty else None
        if woj:
            p, reszta = woj[1], tokeny[woj[1]].sep.lstrip()[1:]  # separator za nawiasem zamykającym
            kontynuacja = _kontynuacja_listy(tokeny, p, reszta, powiaty)
            if kontynuacja is None or not _szukaj(tokeny, kontynuacja, indeks):
                p = pozycje[-1].koniec  # lista się kończy: nawias zostaje do zwykłego rozpoznania
                break
            pozycje[-1].woj = woj
            p = kontynuacja
            continue
        kontynuacja = _kontynuacja_listy(tokeny, p, tokeny[p].sep, powiaty)
        if kontynuacja is None:
            break
        p = kontynuacja
    return pozycje


def _kontynuacja_listy(tokeny: list[Token], p: int, sep: str, srednik: bool = False) -> int | None:
    """Indeks tokenu następnej nazwy listy, gdy po nazwie kończącej się przed `p` lista trwa; inaczej None.

    `sep` to odstęp między nazwą (lub nawiasem) a tokenem `p`. `srednik`: średnik rozdziela pozycje listy (powiatów)
    tak samo jak przecinek; w innych listach średnik kończy listę.
    """
    n = len(tokeny)
    if "\n" in sep or "." in sep or (";" in sep and not srednik):
        return None
    q = p
    if tokeny[q].zlozony in _LACZNIKI and (not sep.strip() or sep.strip() == ","):
        q += 1
    elif tokeny[q].zlozony == "a" and q + 1 < n and tokeny[q + 1].zlozony == "takze":
        q += 2
    elif "," not in sep and not (srednik and ";" in sep):
        return None
    if q >= n or "\n" in tokeny[q].sep or ("." in tokeny[q].sep):
        return None
    return q


def _przyimek_przed(tokeny: list[Token], i: int) -> bool:
    return i > 0 and tokeny[i - 1].zlozony in _PRZYIMKI_MIEJSCA


def _naglowek_listy(tokeny: list[Token], koniec_woj: int, znacznik: int) -> bool:
    """Czy województwo kończące się przed `koniec_woj` jest nagłówkiem listy powiatów od tokenu `znacznik`.

    Tak, gdy lista jest w liczbie mnogiej („powiaty:”) albo województwo oddziela od niej dwukropek lub myślnik
    („woj. lubelskie - powiat chełmski”). „woj. lubelskie, powiat chełmski” to osobne wzmianki.
    """
    if tokeny[znacznik].zlozony in _POW_MNOGA:
        return True
    return any(c in tokeny[k].sep for k in range(koniec_woj, znacznik + 1) for c in ":-\u2013\u2014")


def _po_dla(tokeny: list[Token], poczatek: int) -> bool:
    """Czy tuż przed `poczatek` (do trzech wyrazów, w tym samym zdaniu) stoi „dla”: „dla powiatu”, „dla mieszkańców powiatu”."""
    if poczatek < 0:
        return False
    for k in range(poczatek - 1, max(poczatek - 4, -1), -1):
        if not _bez_konca_zdania(tokeny, k + 1, poczatek + 1):
            return False
        if tokeny[k].zlozony == "dla":
            return True
    return False


def _w_przed(tokeny: list[Token], poczatek: int) -> bool:
    """Czy znacznik od `poczatek` poprzedza przyimek „w”/„we” („w powiecie”, „w gminie”)."""
    return poczatek > 0 and tokeny[poczatek - 1].zlozony in ("w", "we")


def _kraina_po(tokeny: list[Token], nastepny: int, ind: _Indeksy) -> bool:
    """Czy po jednowyrazowej nazwie stoi człon nazwy własnej spoza słownika gmin: „Kotlinie Kłodzkiej”, „Górach Stołowych”.

    Nazwa regionu geograficznego („Kotlina Kłodzka”, „Góry Stołowe”, „Puszcza Białowieska”) nie jest gminą o nazwie
    pierwszego wyrazu. Kolejny wyraz wielką literą po zwykłym odstępie, w formie przymiotnika (-ej, -ych, -ich,
    -iego...), który sam nie jest gminą, tworzy taką nazwę.
    """
    if nastepny >= len(tokeny):
        return False
    t = tokeny[nastepny]
    if not t.wielka or t.cyfra or not t.sep or not _SEP_PROSTY.fullmatch(t.sep) or len(t.zlozony) < 5:
        return False
    if not t.zlozony.endswith(tuple(KONCOWKI_PRZYMIOTNIKA)):
        return False
    return not _szukaj(tokeny, nastepny, ind.gminy)


def _slowo_dozwolone(slowo: str, token: Token, wielkie: bool) -> bool:
    if slowo in _TYLKO_ZNACZNIK:
        return False
    if slowo in _NIE_NA_POCZATKU_ZDANIA and (token.poczatek_zdania or wielkie):
        return False
    return True


def _nazwa_dozwolona(grupa: _Grupa, token: Token, wielkie: bool) -> bool:
    if len(grupa.wyrazy) != 1:
        return True
    return _slowo_dozwolone(grupa.wyrazy[0], token, wielkie)


def _jest_miastem(kod: str) -> bool:
    return sl.jednostka(kod).rodzaj in ("miejska", "miejsko-wiejska")


def _miasto_zaraz_po(tokeny: list[Token], nastepny: int, ind: _Indeksy) -> int:
    """Długość (w tokenach) nazwy gminy stojącej tuż po poprzednim wyrazie, po zwykłym odstępie; 0, gdy jej nie ma."""
    if nastepny < len(tokeny) and tokeny[nastepny].wielka and tokeny[nastepny].sep and _SEP_PROSTY.fullmatch(tokeny[nastepny].sep):
        znaleziono = _szukaj(tokeny, nastepny, ind.gminy)
        if znaleziono:
            return znaleziono[0]
    return 0


def _kontekst_sportowy(tokeny: list[Token], i: int) -> int:
    """Siła kontekstu sportowego zdania z tokenem `i`: 2 (kibice, klub, drużyna, piłkarze, kolejka, liga...), 1 (tylko „mecz”), 0.

    Przeszukiwanie jest ograniczone do `_OKNO_SPORTU` tokenów w każdą stronę (zdanie bywa bardzo długie).
    """
    n = len(tokeny)
    sila = 0
    for kierunek in (-1, 1):
        k = i
        for _ in range(_OKNO_SPORTU):
            if kierunek < 0:
                if tokeny[k].poczatek_zdania:
                    break
                k -= 1
            else:
                k += 1
                if k >= n or tokeny[k].poczatek_zdania:
                    break
            z = tokeny[k].zlozony
            if z in _SPORT_WYRAZY or z.startswith(_SPORT_PREFIKSY):
                return 2
            if z.startswith(_SPORT_SLABY_PREFIKSY) and not z.startswith(_SPORT_NIE):
                sila = 1
    return sila


def _blokada_klubu(tokeny: list[Token], i: int, ind: _Indeksy) -> tuple[int, int, bool]:
    """(liczba tokenów do pominięcia, długość nazwy klubu, czy blokada jest bezsporna), gdy od `i` stoi nazwa klubu.

    „Wisły Kraków”, „Legii Warszawa”, „Kibice Wisły”. Nazwa klubu (w każdym przypadku) blokuje miasto po niej; miasto
    zdarzenia w tym samym zdaniu zostaje. Bez miasta za nią nazwa blokuje samą siebie tylko przy kontekście klubowym
    (słowo z kręgu sportu: „Kibice Wisły zatrzymani w Płocku”) i nie po przyimku z miejscownikiem („w Wiśle” to
    miejsce); bez takiego słowa zostaje gminą (gmina Wisła istnieje). Samo słowo „mecz/mecze” nie czyni nazwy klubem:
    „W Wiśle i w Ustroniu odwołano mecze.” daje oba miejsca, a „Mecz Wisły w Płocku” blokuje nazwę jako spór
    (wycięcie, pewność najwyżej 0,75). Bezsporna jest blokada ze słowem klubowym albo samym meczem po nazwie z miastem
    klubu („Wisła Kraków przegrała mecz”); bez żadnego słowa sportowego („Wisła Kraków zaginęła w Warszawie”) to
    heurystyka sporna.
    """
    klub = _szukaj(tokeny, i, ind.kluby)
    if not klub:
        return 0, 0, True
    sport = _kontekst_sportowy(tokeny, i)
    miasto = _miasto_zaraz_po(tokeny, i + klub[0], ind)
    if miasto:
        return klub[0] + miasto, klub[0], sport > 0
    if sport == 0 or (i > 0 and tokeny[i - 1].zlozony in _PRZYIMKI_MIEJSCOWNIKA):
        return 0, 0, True
    return klub[0], klub[0], sport == 2


def _blokada_rzeki(
    tokeny: list[Token], i: int, dlugosc: int, grupy: list[_Grupa], hydrologia: bool, ind: _Indeksy,
) -> tuple[int, bool]:
    """(liczba tokenów do pominięcia, czy blokada jest bezsporna), gdy nazwa gminy jest w tekście rzeką.

    Rzeka: po „na/nad/rzeka”, z drugim członem „Kłodzka/Łużycka”, po słowie hydrologicznym tuż przed nazwą, w tekście
    o stanie wód (hydrologia) albo tuż przed nazwą innego miasta („Bug Wyszków”; kluby załatwia `_blokada_klubu`).
    Bezsporne (nie obniżają pewności wyniku) są tylko blokady z jawnym znacznikiem rzeki: „Nysa Kłodzka/Łużycka”
    i „na/nad/rzeka X”. Reszta to heurystyki sporne: wycięte miejsce obniża pewność wyniku do `PEWNOSC_PO_WYCIECIU_MAX`.
    """
    nazwy = {g.wyrazy for g in grupy}
    if not nazwy & _RZEKI:
        return 0, True
    nastepny = i + dlugosc
    if nastepny < len(tokeny) and nazwy == {("nysa",)} and tokeny[nastepny].zlozony.startswith(_DRUGI_CZLON_RZEKI):
        return dlugosc + 1, True
    if i > 0 and tokeny[i - 1].zlozony in _PRZED_RZEKA:
        return dlugosc, True
    for k in (i - 1, i - 2):  # „Poziom Wisły”, „stan wód Wisły”, „fala kulminacyjna Bugu” (do dwóch wyrazów, to samo zdanie)
        if k < 0 or not _bez_konca_zdania(tokeny, k + 1, i + 1):
            break
        if tokeny[k].zlozony in _HYDRO_PRZED_RZEKA:
            return dlugosc, False
    if hydrologia:
        return dlugosc, False
    return (dlugosc, False) if _miasto_zaraz_po(tokeny, nastepny, ind) else (0, True)


def _szukaj_trafien(tokeny: list[Token], wielkie: bool, hydrologia: bool) -> tuple[list[_Trafienie], list[_Trafienie]]:
    """Przechodzi po tokenach i zbiera trafienia; ulice, wsie i dzielnice są pomijane.

    Zwraca (trafienia, blokady). Blokady to nazwy gmin, które wycięła sporna heurystyka (rzeka, klub, kraina): nie
    należą do wyniku, ale `geokoduj` obniża pewność, gdy takie miejsce byłoby inaczej w wyniku. Blokady bezsporne
    (np. klub w zdaniu o sporcie, „na Wiśle”) nie są zapisywane.
    """
    ind = _indeksy()
    n = len(tokeny)
    uzyte = [False] * n
    trafienia: list[_Trafienie] = []
    blokady: list[_Trafienie] = []

    def zablokuj(poczatek: int, powod: str) -> None:
        """Zapisuje nazwę gminy od `poczatek`, wyciętą przez heurystykę `powod` (jeśli takiej nazwy tam nie ma, nic)."""
        if poczatek >= n or not tokeny[poczatek].wielka:
            return
        znaleziono = _szukaj(tokeny, poczatek, ind.gminy)
        if not znaleziono:
            return
        dlugosc, grupy = znaleziono
        grupy = [g for g in grupy if _nazwa_dozwolona(g, tokeny[poczatek], wielkie)]
        if grupy:
            blokady.append(_Trafienie(
                poczatek, poczatek + dlugosc, "gmina", "samodzielne", _kody(grupy), kontekst_wielkich=wielkie,
                bez_przyimka=not _przyimek_przed(tokeny, poczatek), blokada=powod))
    woj_lancuchy: dict[int, set[str]] = defaultdict(set)  # indeks po pozycji: województwa każdego łańcucha
    ostatnie_woj: _Trafienie | None = None
    numer_lancucha = 0

    def dodaj(h: _Trafienie) -> None:
        nonlocal ostatnie_woj
        trafienia.append(h)
        if h.typ == "woj":
            ostatnie_woj = h
            if h.kody:
                woj_lancuchy[h.lancuch].add(h.kody[0][:2])

    def zakres_przed(start: int) -> set[str]:
        if ostatnie_woj is not None and start - ostatnie_woj.koniec <= 3:
            return set(woj_lancuchy[ostatnie_woj.lancuch])
        return set()

    i = 0
    while i < n:
        if uzyte[i]:
            i += 1
            continue
        znacznik = _znacznik(tokeny, i)
        if znacznik in ("wies", "ulica"):
            koniec = _pomin_nazwe(tokeny, i + 1, 6 if znacznik == "ulica" else 3)
            for k in range(i, koniec):
                uzyte[k] = True
            i = max(koniec, i + 1)
            continue
        if znacznik == "dzielnica":
            znaleziono = _szukaj(tokeny, i + 1, ind.dzielnice) if i + 1 < n else None
            if znaleziono:
                dlugosc, grupy = znaleziono
                dodaj(_Trafienie(i + 1, i + 1 + dlugosc, "gmina", "dzielnica", _kody(grupy)))
                koniec = i + 1 + dlugosc
            else:
                koniec = max(_pomin_nazwe(tokeny, i + 1, 3), i + 1)
            for k in range(i, koniec):
                uzyte[k] = True
            i = koniec
            continue
        if znacznik in ("woj", "pow", "gm", "miasto"):
            p = i + 1
            if znacznik in ("gm", "miasto"):
                while p < n and (tokeny[p].zlozony in _MODYFIKATORY_GMINY or (tokeny[p].zlozony == "st" and znacznik == "miasto")):
                    p += 1
            indeks = {"woj": ind.wojewodztwa, "pow": ind.powiaty, "gm": ind.gminy, "miasto": ind.gminy}[znacznik]
            pozycje = _wczytaj_lancuch(tokeny, p, indeks, powiaty=znacznik == "pow")
            if pozycje:
                numer_lancucha += 1
                zakres = zakres_przed(i) if znacznik == "pow" else set()
                # województwo przed listą jest jej nagłówkiem („woj. X - powiaty: A, B”), a nie osobnym zasięgiem;
                # „dla woj. X, powiat Y” (liczba pojedyncza po przecinku) to dwie wzmianki; „woj. X: w powiecie Y” też
                # (węższe miejsce z „w” nie jest listą pod nagłówkiem: województwo zostaje, zob. `_przylegle`)
                naglowek = bool(zakres) and _naglowek_listy(tokeny, ostatnie_woj.koniec, i) and not _w_przed(tokeny, i)
                koniec_lancucha = pozycje[-1].koniec
                lancuch = numer_lancucha
                for poz in pozycje:
                    zakres_pozycji, doprecyzowuje = (set(zakres), naglowek)
                    if poz.woj:  # „A (woj. X)” w środku listy: województwo doprecyzowuje tę nazwę
                        numer_lancucha += 1
                        dodaj(_Trafienie(
                            poz.woj[0] + 1, poz.woj[1], "woj", "znacznik", poz.woj[2], lancuch=numer_lancucha,
                            lancuch_koniec=poz.woj[1], poczatek=poz.woj[0]))
                        for k in range(poz.woj[0], poz.woj[1]):
                            uzyte[k] = True
                        zakres_pozycji, doprecyzowuje = {poz.woj[2][0][:2]}, True
                    dodaj(_Trafienie(
                        poz.start, poz.koniec, {"woj": "woj", "pow": "pow"}.get(znacznik, "gmina"),
                        "lista" if znacznik == "pow" else "znacznik", poz.kody, znacznik="" if znacznik in ("woj", "pow") else znacznik,
                        lancuch=lancuch, lancuch_koniec=koniec_lancucha, zakres=zakres_pozycji,
                        poczatek=i, zakres_doprecyzowuje=doprecyzowuje, zakres_z_naglowka=naglowek and not poz.woj))
                    for k in range(poz.start, poz.koniec):
                        uzyte[k] = True
                for k in range(i, p):
                    uzyte[k] = True
                i = koniec_lancucha
                continue
            i += 1
            continue
        # województwo przed „powiaty:” / „gmina”: „lubelskiego - powiaty: ...”
        znaleziono = _szukaj(tokeny, i, ind.wojewodztwa)
        if znaleziono:
            dlugosc, grupy = znaleziono
            j = i + dlugosc
            if j < n and _SEP_ZAKRESU.fullmatch(tokeny[j].sep) and _znacznik(tokeny, j) in ("pow", "gm"):
                numer_lancucha += 1
                dodaj(_Trafienie(i, j, "woj", "zakres", _kody(grupy), lancuch=numer_lancucha, lancuch_koniec=j, poczatek=i))
                for k in range(i, j):
                    uzyte[k] = True
                i = j
                continue
        znaleziono = _szukaj(tokeny, i, ind.regiony)
        if znaleziono:
            dlugosc, grupy = znaleziono
            numer_lancucha += 1
            dodaj(_Trafienie(i, i + dlugosc, "region", "region", _kody(grupy), lancuch=numer_lancucha, lancuch_koniec=i + dlugosc, poczatek=i))
            for k in range(i, i + dlugosc):
                uzyte[k] = True
            i += dlugosc
            continue
        klub, dlugosc_klubu, klub_bezsporny = _blokada_klubu(tokeny, i, ind)
        if klub:
            if not klub_bezsporny:
                zablokuj(i, "klub")
                if klub > dlugosc_klubu:
                    zablokuj(i + dlugosc_klubu, "klub")
            for k in range(i, i + klub):
                uzyte[k] = True
            i += klub
            continue
        # samodzielna nazwa gminy lub miasta
        przyimek = _przyimek_przed(tokeny, i)
        znaleziono = _szukaj(tokeny, i, ind.gminy)
        if znaleziono:
            dlugosc, grupy = znaleziono
            grupy = [g for g in grupy if _nazwa_dozwolona(g, tokeny[i], wielkie)]
            if not grupy:
                i += 1
                continue
            po_imieniu = False
            if not przyimek:
                rola = _po_imieniu(tokeny, i, dlugosc, ind)
                if rola == _OSOBA:  # „Andrzej Kalisz”: nazwisko, nie miejsce (bezsporne: lista imion, imię nie jest gminą)
                    for k in range(i, i + dlugosc):
                        uzyte[k] = True
                    i += dlugosc
                    continue
                po_imieniu = rola == _MOZE_OSOBA
            # dzielnice Warszawy nie dają gmin („na Bielanach”), chyba że gmina ma dłuższą nazwę („Wola Krzysztoporska”)
            dzielnica = _szukaj(tokeny, i, ind.dzielnice)
            if dzielnica and dzielnica[0] >= dlugosc:
                for k in range(i, i + dzielnica[0]):
                    uzyte[k] = True
                i += dzielnica[0]
                continue
            if dlugosc == 1 and _kraina_po(tokeny, i + 1, ind) and not all(sl.jednostka(k).rodzaj == "miejska" for k in _kody(grupy)):
                rzeka_dwuczlonowa, rzeka_pewna = _blokada_rzeki(tokeny, i, dlugosc, grupy, hydrologia, ind)
                if not (rzeka_dwuczlonowa and rzeka_pewna):  # „Nysa Kłodzka” to rzeka (bezsporna), a nie kraina
                    zablokuj(i, "kraina")
                for k in range(i, i + 2):  # „Kotlinie Kłodzkiej”: region geograficzny, nie gmina Kotlin
                    uzyte[k] = True
                i += 2
                continue
            pominiete, rzeka_bezsporna = _blokada_rzeki(tokeny, i, dlugosc, grupy, hydrologia, ind)
            if pominiete:
                if not rzeka_bezsporna:
                    zablokuj(i, "rzeka")
                for k in range(i, i + pominiete):
                    uzyte[k] = True
                i += pominiete
                continue
            kody = _kody(grupy)
            # homonimię liczymy przed filtrem przyimka; bez przyimka wystarczy, że wśród kandydatów jest miasto
            if not przyimek and not any(sl.jednostka(k).rodzaj == "miejska" for k in kody):
                i += 1
                continue
            skrot = False
            if przyimek and not any(_jest_miastem(k) for k in kody):
                konkurenci = [g for g in _skrocone(tokeny, i, ind.gminy, dlugosc) if _slowo_dozwolone(g.wyrazy[0], tokeny[i], wielkie)]
                if konkurenci:  # „w Grodzisku”: jest gmina Grodzisk, ale też Grodzisk Mazowiecki i Wielkopolski
                    kody = kody + [k for k in _kody(konkurenci) if k not in kody]
                    skrot = True
            dodaj(_Trafienie(i, i + dlugosc, "gmina", "samodzielne", kody, kontekst_wielkich=wielkie, bez_przyimka=not przyimek,
                             skrot=skrot, po_imieniu=po_imieniu))
            for k in range(i, i + dlugosc):
                uzyte[k] = True
            i += dlugosc
            continue
        # skrót bez gminy o takiej nazwie („w Mińsku” - Mińsk Mazowiecki): brak, ale z uwagą
        if (przyimek and tokeny[i].wielka and tokeny[i].zlozony not in _GENERYCZNE_PIERWSZE
                and tokeny[i].zlozony not in _NIE_NAZWY_GMIN and not _kraina_po(tokeny, i + 1, ind)):
            konkurenci = [g for g in _skrocone(tokeny, i, ind.gminy, 1)
                          if g.wyrazy[0] not in _GENERYCZNE_PIERWSZE and _slowo_dozwolone(g.wyrazy[0], tokeny[i], wielkie)]
            if konkurenci and not (_nazwa_to_rzeka(konkurenci)):
                dodaj(_Trafienie(i, i + 1, "gmina", "samodzielne", _kody(konkurenci), kontekst_wielkich=wielkie, skrot=True))
                uzyte[i] = True
                i += 1
                continue
        i += 1
    return trafienia, blokady


_OSOBA = "osoba"  # nazwa po imieniu to nazwisko: nie miejsce
_MOZE_OSOBA = "moze-osoba"  # nazwa po imieniu, które samo bywa miejscem lub zwykłym słowem: nazwisko tylko, gdy jest inne miejsce


def _po_imieniu(tokeny: list[Token], i: int, dlugosc: int, ind: _Indeksy) -> str:
    """Czy nazwa gminy bez przyimka, od `i`, jest nazwiskiem: `_OSOBA`, `_MOZE_OSOBA` albo "" (miejsce).

    `_OSOBA` (bezsporne): nazwa tuż po imieniu z listy („Andrzej Kalisz”), albo sama nazwa będąca imieniem, po której
    stoi wyraz wielką literą w tym samym zdaniu, który nie jest gminą („Jarosław Kaczyński”: imię, nie miasto Jarosław).
    `_MOZE_OSOBA`: nazwa po wyrazie, który jest imieniem, ale bywa też czymś innym: nazwą gminy wiejskiej („Hanna
    Kraków”, „Bolesław Kraków”) albo imieniem o odmianie zwykłego wyrazu („Wita Kalisza”: „Wit”, czasownik „wita”).
    Wtedy nazwa odpada tylko wtedy, gdy w tekście jest wyraźne miejsce z przyimkiem (zob. `geokoduj`); inaczej zostaje
    miejscem. Nie jest osobą, gdy poprzedni wyraz sam jest miastem („Jarosław Przemyśl”: trasa, dwa miejsca), stoi po
    „św.”, „ul.”, „al.”, „im.” („Kościół św. Anny Lubartów”) ani gdy nazwa otwiera definicję „X to nazwa…” („Hanna
    Lublin to nazwa kawiarni”).
    """
    t = tokeny[i]
    nastepny = i + dlugosc
    if i > 0 and t.sep and _SEP_PROSTY.fullmatch(t.sep) and tokeny[i - 1].wielka:
        poprzedni = tokeny[i - 1]
        imie = jest_imieniem(poprzedni.zlozony)
        # „Wit” przed nazwą w środku zdania („Wita Kalisza”); na początku zdania „Wita” to czasownik
        dwuznaczne = not imie and jest_imieniem_dwuznacznym(poprzedni.zlozony) and (
            not poprzedni.poczatek_zdania or poprzedni.zlozony == "wit")
        if imie or dwuznaczne:
            if i > 1 and tokeny[i - 2].zlozony in _PRZED_PATRONEM:  # patron: „św. Anny Lubartów”, „ul. Anny Jantar Opole”
                return ""
            poprzednia = _szukaj(tokeny, i - 1, ind.gminy)
            wlasna_gmina = bool(poprzednia) and poprzednia[0] == 1
            if wlasna_gmina and any(_jest_miastem(k) for k in _kody(poprzednia[1])):
                return ""  # „Jarosław Przemyśl”: dwa miasta, a nie osoba
            if wlasna_gmina or dwuznaczne:
                definicja = nastepny < len(tokeny) and tokeny[nastepny].zlozony == "to"
                return "" if definicja else _MOZE_OSOBA
            return _OSOBA
    if dlugosc == 1 and nastepny < len(tokeny) and jest_imieniem(t.zlozony):
        n = tokeny[nastepny]
        osoba = (n.wielka and not n.cyfra and not n.poczatek_zdania and bool(n.sep) and bool(_SEP_PROSTY.fullmatch(n.sep))
                 and not _szukaj(tokeny, nastepny, ind.gminy))
        return _OSOBA if osoba else ""
    return ""


def _nazwa_to_rzeka(grupy: list[_Grupa]) -> bool:
    return bool({g.wyrazy[:1] for g in grupy} & _RZEKI)


def _przypisz_zakres_po(trafienia: list[_Trafienie]) -> None:
    """Zakres „po”: powiaty bez województwa przed listą dostają województwo stojące tuż za nią."""
    woje = [w for w in trafienia if w.typ == "woj" and w.kody]
    if not woje:
        return
    starty = [w.start for w in woje]
    lancuchy: dict[int, set[str]] = defaultdict(set)
    for w in woje:
        lancuchy[w.lancuch].add(w.kody[0][:2])
    for h in trafienia:
        if h.typ == "pow" and not h.zakres:
            idx = bisect_left(starty, h.lancuch_koniec)
            if idx < len(woje) and starty[idx] - h.lancuch_koniec <= 3:
                h.zakres = set(lancuchy[woje[idx].lancuch])
                h.zakres_doprecyzowuje = True  # „A, B (woj. X)”: województwo za listą jest dopiskiem do niej


# --------------------------------------------------------------------------- rola jednostki organizacyjnej

def _czlon_jednostki(token: Token) -> bool:
    """Czy wyraz może należeć do nazwy jednostki („Komenda”, „Powiatowej”, „KPP”, „komisariatu”, „Policji”)."""
    z = token.zlozony
    return (token.wielka or z.startswith(_JEDNOSTKA_PREFIKSY) or z in _JEDNOSTKA_WYRAZY or z in _JEDNOSTKA_SKROTY
            or z.startswith(_JEDNOSTKA_PRZEDROSTKI_MALE) or z in _JEDNOSTKA_SLOWA_MALE)


def _jednostka_przed(tokeny: list[Token], start: int) -> str | None:
    """Czy nazwa stoi w „Komenda ... Policji w X”: zwraca poziom jednostki (wojewodztwo/powiat/gmina) albo None.

    Przed „w” szukamy wstecz wyłącznie wyrazów nazwy jednostki (wielkie litery, skróty KPP/KMP/KWP/KSP/KP/JRG/PSP,
    „komisariatu” małą literą), więc „... Komendy Wojewódzkiej Policji w Lublinie zatrzymali w Chełmie” nie
    przenosi roli na Chełm.
    """
    if start == 0 or tokeny[start - 1].zlozony not in ("w", "we"):
        return None
    poziom, znaleziono = sl.GMINA, False
    k = start - 2
    while k >= 0 and start - 2 - k < 6 and _czlon_jednostki(tokeny[k]):
        if any(c in tokeny[k + 1].sep for c in _KONIEC_ZDANIA):  # granica zdania
            break
        z = tokeny[k].zlozony
        # „km” to też kilometry: jednostką jest tylko „KM PSP”
        km_psp = z != "km" or (k + 1 < len(tokeny) and tokeny[k + 1].zlozony == "psp")
        if z.startswith(_JEDNOSTKA_PREFIKSY) or z in _JEDNOSTKA_WYRAZY or (z in _JEDNOSTKA_SKROTY and km_psp):
            znaleziono = True
        if z.startswith("wojewodzk") or z == "kwp" or (z == "psp" and k > 0 and tokeny[k - 1].zlozony == "kw"):
            poziom = sl.WOJEWODZTWO
        elif poziom != sl.WOJEWODZTWO and (
                z.startswith("powiatow") or z == "kpp" or (z == "kp" and k + 1 < len(tokeny) and tokeny[k + 1].zlozony == "psp")):
            poziom = sl.POWIAT
        k -= 1
    return poziom if znaleziono else None


# --------------------------------------------------------------------------- rozstrzyganie

def _wartosc_kodu_gminy(kod: str) -> float:
    j = sl.jednostka(kod)
    return PEWNOSC_GMINA_SAMODZIELNA["grodzka" if j.grodzka else j.rodzaj]


def _dokladnosc(kod: str) -> str:
    return sl.poziom_kodu(kod)


def _rodzaj(typ: str) -> str:
    return {"woj": sl.WOJEWODZTWO, "region": sl.WOJEWODZTWO, "pow": sl.POWIAT, "gmina": sl.GMINA}[typ]


@dataclass(slots=True)
class _Rozstrzygniecie:
    kody: tuple[str, ...]
    pewnosc: float
    uwagi: tuple[str, ...] = ()
    odrzucone: bool = False  # nazwa wieloznaczna bez rozstrzygnięcia: nic nie przyjęto
    sprzeczny: bool = False  # powiat z tekstu wyklucza nazwę (zostaje sam powiat, z obniżoną pewnością wyniku)
    sporny: bool = False  # powiat wykluczył nazwę, która bez niego byłaby przyjęta: wynik nie wyżej niż PEWNOSC_PO_WYCIECIU_MAX


def _wspolny_poziom(kody: list[str]) -> tuple[str, int] | None:
    for dlugosc in (4, 2):
        if len({k[:dlugosc] for k in kody}) == 1:
            return kody[0][:dlugosc], dlugosc
    return None


def _spadek(kody: list[str], uwagi: list[str]) -> _Rozstrzygniecie:
    wspolny = _wspolny_poziom(kody)
    uwagi = uwagi + ["homonim"]
    if wspolny and wspolny[1] == 4:
        return _Rozstrzygniecie((wspolny[0],), PEWNOSC_SPADEK_DO_POWIATU, tuple(uwagi + ["spadek-do-powiatu"]))
    if wspolny and wspolny[1] == 2:
        return _Rozstrzygniecie((wspolny[0],), PEWNOSC_SPADEK_DO_WOJEWODZTWA, tuple(uwagi + ["spadek-do-wojewodztwa"]))
    return _Rozstrzygniecie((), 0.0, tuple(uwagi + ["niejednoznaczne"]), odrzucone=True)


def _rozstrzygnij_woj(h: _Trafienie) -> _Rozstrzygniecie:
    pewnosc = {"znacznik": PEWNOSC_WOJ_ZNACZNIK, "zakres": PEWNOSC_WOJ_ZAKRES, "region": PEWNOSC_REGION}[h.tryb]
    return _Rozstrzygniecie(tuple(h.kody[:1]), pewnosc)


@lru_cache(maxsize=1)
def _powiaty_o_nazwie_miast() -> dict[str, str]:
    """Kod powiatu grodzkiego -> kod powiatu ziemskiego o jego nazwie (tabela `_POWIAT_O_NAZWIE_MIASTA`, na danych)."""
    s = sl.slownik()
    ziemskie = {(p.nazwa, p.kod[:2]): p.kod for p in s.powiaty if p.rodzaj == "ziemski"}
    wynik: dict[str, str] = {}
    for p in s.powiaty:
        nazwa_powiatu = _POWIAT_O_NAZWIE_MIASTA.get(p.nazwa) if p.rodzaj == "grodzki" else None
        if nazwa_powiatu and (nazwa_powiatu, p.kod[:2]) in ziemskie:
            wynik[p.kod] = ziemskie[(nazwa_powiatu, p.kod[:2])]
    return wynik


def _zgodny_z_powiatem(kod: str, powiaty: set[str]) -> bool:
    """Czy kod gminy leży w jednym z powiatów albo jest miastem na prawach powiatu o nazwie takiego powiatu."""
    return kod[:4] in powiaty or _powiaty_o_nazwie_miast().get(kod[:4]) in powiaty


def _w_wojewodztwie(kod: str, wojewodztwa: set[str]) -> bool:
    return kod[:2] in wojewodztwa


def _dopasuj(kontekst: int | Callable[[str, set[str]], bool]) -> Callable[[str, set[str]], bool]:
    """Kontekst to długość kodu (województwo 2, powiat 4) albo funkcja (kod, zbiór) -> zgodność."""
    if callable(kontekst):
        return kontekst
    return lambda kod, zbior: kod[:kontekst] in zbior


def _zawez(kandydaci: list[str], konteksty: list[tuple[set[str], int | Callable[[str, set[str]], bool]]]) -> tuple[list[str], bool]:
    """Zawęża kandydatów kontekstem (zbiory kodów województw lub powiatów); zwraca (kandydaci, użyto_kontekstu)."""
    for zbior, kontekst in konteksty:
        if zbior:
            zgodny = _dopasuj(kontekst)
            podzbior = [k for k in kandydaci if zgodny(k, zbior)]
            if podzbior and len(podzbior) < len(kandydaci):
                return podzbior, True
            if podzbior:
                return kandydaci, False
    return kandydaci, False


def _zawez_skrot(kandydaci: list[str], konteksty: list[tuple[set[str], int | Callable[[str, set[str]], bool]]]) -> tuple[list[str], bool]:
    """Skrócona nazwa przyjmuje tylko kandydatów potwierdzonych kontekstem (nawet jeśli kandydat jest jeden)."""
    for zbior, kontekst in konteksty:
        if zbior:
            zgodny = _dopasuj(kontekst)
            podzbior = [k for k in kandydaci if zgodny(k, zbior)]
            if podzbior:
                return podzbior, True
    return kandydaci, False


def _rozstrzygnij_powiat(
    h: _Trafienie, wszystkie_woj: set[str], gmina_przed: tuple[str, ...] = (), gmina_po: tuple[str, ...] = (),
) -> _Rozstrzygniecie:
    """Rozstrzyga nazwę powiatu. `gmina_przed`: kody gminy, której powiat jest dopiskiem („Opole (powiat opolski)”);
    `gmina_po`: kody gminy wskazanej tuż za powiatem lub w nawiasie za nim („powiat opolski (gmina Poniatowa)”).

    Nazwa powiatu bywa wieloznaczna („opolski”: lubelskie i opolskie; „bielski”, „krośnieński”). Gdy województwo nie
    rozstrzyga, powiat zgodny z gminą stojącą tuż przed nim („Opole” - 1609, nie 0612) jest dopiskiem do niej, a z
    gminą stojącą tuż za nim („Poniatowa” - 0612) jest jej powiatem. Gdy obie gminy wskazują różne powiaty
    („miasto Opole, powiat opolski (gmina Poniatowa)”), powiat zostaje nierozstrzygnięty (uwaga `sprzeczne-gminy`).
    """
    kandydaci = list(h.kody)
    uwagi: list[str] = []
    if len(kandydaci) > 1:
        kandydaci, uzyto = _zawez(kandydaci, [(h.zakres, 2), (wszystkie_woj, 2)])
        if uzyto:
            uwagi.append("kontekst")
    if len(kandydaci) > 1 and (gmina_przed or gmina_po):
        przed = [k for k in kandydaci if any(_zgodny_z_powiatem(g, {k}) for g in gmina_przed)]
        po = [k for k in kandydaci if any(_zgodny_z_powiatem(g, {k}) for g in gmina_po)]
        if przed and po and not set(przed) & set(po):  # sąsiednie gminy wskazują różne powiaty: nie wybieramy żadnego
            return _Rozstrzygniecie((), 0.0, ("homonim", "niejednoznaczne", "sprzeczne-gminy"), odrzucone=True)
        zgodne = [k for k in przed if k in po] if przed and po else (przed or po)
        if len(zgodne) == 1:
            kandydaci = zgodne
            uwagi.append("kontekst")
    if len(kandydaci) == 1:
        return _Rozstrzygniecie((kandydaci[0],), PEWNOSC_PO_KONTEKSCIE if uwagi else PEWNOSC_POWIAT, tuple(uwagi))
    if len(h.kody) > 1:
        return _Rozstrzygniecie((), 0.0, ("homonim", "niejednoznaczne"), odrzucone=True)
    return _Rozstrzygniecie((), 0.0, ("brak-kodu",), odrzucone=True)


def _preferowane_miasto(kandydaci: list[str]) -> str | None:
    """Miasto zamiast gminy wiejskiej o tej samej nazwie: tylko gdy wszystkie gminy o tej nazwie są w jednym województwie.

    Miasto na prawach powiatu obok gminy wiejskiej z innego województwa („Leszno”, „Olsztyn”) nie wygrywa:
    bez kontekstu nie wiadomo, o które chodzi. Liczą się gminy o tej samej nazwie; kandydaci o innej nazwie,
    dopasowani tylko fleksją („Siedlcach” pasuje też do gminy Siedlec), nie blokują miasta.
    """
    po_nazwie: dict[str, list[str]] = defaultdict(list)
    for k in kandydaci:
        po_nazwie[sl.jednostka(k).nazwa].append(k)
    wybrane: list[str] = []
    for kody in po_nazwie.values():
        if len({k[:2] for k in kody}) != 1:
            continue
        grodzkie = [k for k in kody if sl.jednostka(k).grodzka]
        if len(grodzkie) == 1:
            wybrane.append(grodzkie[0])
        elif len(kody) > 1 and len({k[:4] for k in kody}) == 1:
            miejskie = [k for k in kody if sl.jednostka(k).rodzaj == "miejska"]
            if len(miejskie) == 1:
                wybrane.append(miejskie[0])
    return wybrane[0] if len(wybrane) == 1 else None


def _rozstrzygnij_gmine(
    h: _Trafienie, tokeny: list[Token], ctx_pow: set[str], ctx_woj: set[str], obok: frozenset[str] = frozenset(),
    obok_woj: frozenset[str] = frozenset(),
) -> _Rozstrzygniecie:
    """Rozstrzyga nazwę gminy kontekstem. `obok`: powiaty wpisane tuż za nazwą („Kraków, powiat pruszkowski”);
    `obok_woj`: województwo dopisane tuż za nazwą („Leszno (woj. mazowieckie)”).

    Dopisek za nazwą (powiat, potem województwo) wygrywa z powiatem i województwem z osobnych zdań, które zostają
    zasięgiem alertu: „Awaria w Lesznie (woj. mazowieckie). Alert dla powiatu leszczyńskiego.” to gmina Leszno na
    Mazowszu. Gdy powiat z innego zdania wskazywałby innego kandydata niż dopisek, wynik jest sporny (najwyżej 0,75).

    Powiat z tekstu, który wyklucza wszystkie kandydaty, daje `sprzeczny` (zostaje sam powiat). Nazwa wieloznaczna
    i skrót sprawdzają wszystkie powiaty z tekstu, nazwa jednoznaczna tylko powiat stojący tuż za nią (inny powiat
    w tekście to osobna wzmianka). Miasto na prawach powiatu jest zgodne z powiatem o swojej nazwie („Leszno” i
    „powiat leszczyński”, „Tarnów” i „powiat tarnowski”).
    """
    kandydaci = list(h.kody)
    uwagi: list[str] = []
    jednostki = {k: sl.jednostka(k) for k in kandydaci}
    if h.znacznik == "gm":  # „gmina X” to nie miasto na prawach powiatu, jeśli jest inna
        reszta = [k for k in kandydaci if not jednostki[k].grodzka]
        kandydaci = reszta or kandydaci
    elif h.znacznik == "miasto":  # „miasto X” to nie gmina wiejska, jeśli jest inna
        miejskie = [k for k in kandydaci if jednostki[k].miejska]
        kandydaci = miejskie or kandydaci
    # dopisek tuż za nazwą ma pierwszeństwo przed powiatem z osobnego zdania („Pożar w Lesznie (powiat pruszkowski).
    # Alert dla powiatu leszczyńskiego.” to Leszno z powiatem pruszkowskim, a nie miasto Leszno)
    ctx_powiatu = set(obok) or ctx_pow
    konteksty = [(ctx_powiatu, _zgodny_z_powiatem), (ctx_woj, _w_wojewodztwie)]
    dopisek_woj = bool(obok_woj) and not obok and any(_w_wojewodztwie(k, set(obok_woj)) for k in kandydaci)
    if dopisek_woj:
        konteksty.insert(0, (set(obok_woj), _w_wojewodztwie))
    kontrola = set(obok) or (ctx_pow if (h.skrot or len(kandydaci) > 1) and not dopisek_woj else set())
    # powiat z osobnego zdania wskazywałby kandydata spoza województwa z dopisku: konflikt, wynik do przeglądu
    konflikt = dopisek_woj and bool(ctx_pow) and any(_zgodny_z_powiatem(k, ctx_pow) for k in kandydaci) and not any(
        _zgodny_z_powiatem(k, ctx_pow) for k in kandydaci if _w_wojewodztwie(k, set(obok_woj)))
    if kontrola and not any(_zgodny_z_powiatem(k, kontrola) for k in kandydaci):
        # powiat z tekstu wyklucza wszystkich kandydatów („Pożar w Lesznie, powiat pruszkowski”, „Kraków, powiat
        # pruszkowski”): zostaje sam powiat (to osobne trafienie), z niską pewnością; nie przechodzimy na województwo
        # tego powiatu ani na miasto spoza niego. Pewność wyniku obniżamy do 0,6, gdy sprzeczny powiat jest dopiskiem do
        # tej nazwy. Powiat z innego zdania to osobna wzmianka: wynik spada tylko do 0,75 (zabezpieczenie strukturalne),
        # i to wtedy, gdy nazwa bez tego powiatu byłaby przyjęta (nazwa wieloznaczna bez rozstrzygnięcia i tak odpada).
        sporny = bool(obok) or bool(_rozstrzygnij_gmine(h, tokeny, set(), ctx_woj, obok_woj=obok_woj).kody)
        return _Rozstrzygniecie((), 0.0, ("powiat-wyklucza", "niejednoznaczne"), odrzucone=True, sprzeczny=bool(obok), sporny=sporny)
    if h.skrot:
        kandydaci, uzyto = _zawez_skrot(kandydaci, konteksty)
        if not uzyto:
            return _Rozstrzygniecie((), 0.0, ("skrot", "niejednoznaczne"), odrzucone=True)
        uwagi += ["skrot", "kontekst"]
    elif len(kandydaci) > 1:
        kandydaci, uzyto = _zawez(kandydaci, konteksty)
        if uzyto:
            uwagi.append("kontekst")
    if len(kandydaci) == 1:
        kod = kandydaci[0]
        if h.tryb == "dzielnica":
            pewnosc = PEWNOSC_DZIELNICA
        elif h.tryb == "znacznik":
            pewnosc = PEWNOSC_PO_KONTEKSCIE if "kontekst" in uwagi else PEWNOSC_GMINA_ZNACZNIK
        else:
            pewnosc = _wartosc_kodu_gminy(kod)
            if h.kontekst_wielkich:
                pewnosc *= WSPOLCZYNNIK_WIELKICH_LITER
            if "kontekst" in uwagi:
                pewnosc = max(pewnosc, PEWNOSC_PO_KONTEKSCIE)
        if h.skrot:
            pewnosc = min(pewnosc, PEWNOSC_SKROT_MAX)
        wynik = _Rozstrzygniecie((kod,), pewnosc, tuple(uwagi))
    else:
        miasto = _preferowane_miasto(kandydaci) if PREFERUJ_MIASTO and h.znacznik != "gm" else None
        if miasto:
            pewnosc = min(PEWNOSC_MIASTO_PREFEROWANE, PEWNOSC_SKROT_MAX) if h.skrot else PEWNOSC_MIASTO_PREFEROWANE
            wynik = _Rozstrzygniecie((miasto,), pewnosc, tuple(uwagi + ["homonim", "preferowane-miasto"]))
        else:
            wynik = _spadek(kandydaci, uwagi)
    if wynik.kody and h.tryb == "samodzielne" and len(wynik.kody[0]) == 7:
        poziom = _jednostka_przed(tokeny, h.start)
        if poziom:
            kod = wynik.kody[0]
            dlugosc = {sl.WOJEWODZTWO: 2, sl.POWIAT: 4, sl.GMINA: 7}[poziom]
            uwagi_jednostki = ["jednostka"] + ([f"spadek-do-{'wojewodztwa' if dlugosc == 2 else 'powiatu'}"] if dlugosc < 7 else [])
            return _Rozstrzygniecie(
                (kod[:dlugosc],), min(wynik.pewnosc, PEWNOSC_JEDNOSTKA_MAX), wynik.uwagi + tuple(uwagi_jednostki), sporny=konflikt)
    if konflikt and wynik.kody:
        wynik.sporny = True
        wynik.uwagi += ("konflikt-kontekstu",)
    return wynik


def _dopisek_powiatu(tokeny: list[Token], koniec_nazwy: int, start_powiatu: int) -> bool:
    """Czy nazwa powiatu od tokenu `start_powiatu` jest dopiskiem do nazwy kończącej się przed `koniec_nazwy`.

    Dopisek: najwyżej 3 wyrazy między nazwą a powiatem, to samo zdanie, bez dwukropka i myślnika; między nimi tylko
    „w” i znacznik powiatu („, w powiecie X”, „(pow. X)”). „A i w powiecie X” to dwie wzmianki.
    """
    if start_powiatu < koniec_nazwy or koniec_nazwy >= len(tokeny) or start_powiatu - koniec_nazwy > 3:
        return False
    if not _bez_konca_zdania(tokeny, koniec_nazwy, start_powiatu) or not _bez_dwukropka(tokeny, koniec_nazwy, start_powiatu - 1):
        return False
    return all(tokeny[k].zlozony in ("w", "we") or tokeny[k].zlozony in _POW for k in range(koniec_nazwy, start_powiatu))


def _powiaty_za_nazwa(
    tokeny: list[Token], h: _Trafienie, starty: list[int], powiaty: list[tuple[_Trafienie, _Rozstrzygniecie]],
) -> frozenset[str]:
    """Powiaty wpisane tuż za nazwą gminy jako dopisek: „Kraków, powiat pruszkowski”, „Zakopane (pow. tatrzański)”.

    Dopisek to powiat (z własnym znacznikiem „powiat/pow./w powiecie”) w odległości najwyżej 3 wyrazów, w tym samym
    zdaniu, bez dwukropka, średnika i myślnika między nimi. Powiat stojący przed nazwą albo dalej to osobna wzmianka.
    """
    idx = bisect_left(starty, h.koniec)
    if idx >= len(powiaty) or not _dopisek_powiatu(tokeny, h.koniec, starty[idx]):
        return frozenset()
    lancuch = powiaty[idx][0].lancuch
    kody: set[str] = set()
    while idx < len(powiaty) and powiaty[idx][0].lancuch == lancuch:
        kody.add(powiaty[idx][1].kody[0])
        idx += 1
    return frozenset(kody)


def _na_oryginal(mapa: MapaPozycji | None, start: int, koniec: int) -> tuple[int, int]:
    """Pozycje [start, koniec) w czystym tekście jako pozycje w oryginale (czysty: NFC, bez znaków niewidocznych)."""
    if mapa is None:
        return start, koniec
    return mapa.na_oryginal(start, koniec)


def _fraza(tekst: str, tokeny: list[Token], h: _Trafienie, mapa: MapaPozycji | None) -> tuple[str, int, int]:
    """Fragment oryginalnego tekstu dla trafienia (`mapa`: pozycje po normalizacji NFC i usunięciu znaków niewidocznych)."""
    start, koniec = _na_oryginal(mapa, tokeny[h.start].start, tokeny[h.koniec - 1].koniec)
    return tekst[start:koniec], start, koniec


# --------------------------------------------------------------------------- zasięg

@dataclass(slots=True)
class _Przyjety:
    kod: str
    pewnosc: float
    h: _Trafienie
    uwagi: tuple[str, ...]
    dopasowanie: int = -1  # indeks w liście dopasowań wyniku

    @property
    def zasieg(self) -> bool:
        """Województwo, region lub powiat wskazane wprost (a nie miejsce jednostki ani spadek homonimu)."""
        return self.h.typ in ("woj", "region", "pow")


def _bez_konca_zdania(tokeny: list[Token], od: int, do: int) -> bool:
    """Czy między tokenami [od, do) nie ma końca zdania ani średnika (spacja przed każdym z nich liczy się)."""
    return not any(c in tokeny[k].sep for k in range(od, do) for c in _KONIEC_ZDANIA)


def _bez_dwukropka(tokeny: list[Token], od: int, do: int) -> bool:
    """Czy między tokenami [od, do] nie ma dwukropka ani myślnika (nagłówek oddzielony od treści)."""
    return not any(c in tokeny[k].sep for k in range(od, min(do + 1, len(tokeny))) for c in ":-\u2013\u2014")


def _przylegle(tokeny: list[Token], szerszy: _Przyjety, wezszy: _Przyjety) -> bool:
    """Czy węższe miejsce doprecyzowuje szersze w zapisie adresowym („w woj. X, w powiecie Y, w gminie Z”, „Z, woj. X”).

    Czysta hierarchia jednego miejsca to tylko: (1) „w” przed każdym poziomem, od szerszego po węższe, rozdzielone
    samym przecinkiem; (2) dopisek za nazwą („Chełm, woj. lubelskie”, „Zakopane (powiat tatrzański)”). Szerszy kod bez
    własnego „w” („Alert RCB, woj. mazowieckie: w mieście Warszawa”, „Alert RCB: powiat tatrzański, w gminie Zakopane”)
    albo oddzielony dwukropkiem lub myślnikiem („Woj. lubelskie: w powiecie chełmskim”) to nagłówek lub wyliczenie
    zasięgu: oba kody zostają. „woj. X, miasto Y” (bez „w”) to też wyliczenie.
    """
    s, w = szerszy.h, wezszy.h
    if s.koniec <= w.start:  # szersze stoi przed węższym: „w” przed obydwoma i sam przecinek między nimi
        if not (w.znacznik or w.typ == "pow") or not _w_przed(tokeny, w.poczatek) or not _w_przed(tokeny, s.poczatek):
            return False
        # „w” węższego miejsca stoi tuż za szerszym: „w powiecie Y, w gminie Z”; wtrącenie („..., zwłaszcza w gminie Z”)
        # to wyliczenie zasięgu, a nie hierarchia jednego miejsca
        return w.poczatek == s.koniec + 1 and _bez_konca_zdania(tokeny, s.koniec, w.start) and _bez_dwukropka(tokeny, s.koniec, w.start)
    if w.koniec <= s.start:  # szersze stoi po węższym
        luka = s.start - w.koniec
        if w.znacznik or w.typ == "pow":
            return luka <= 4 and _bez_konca_zdania(tokeny, w.koniec, s.start)
        # samodzielna nazwa: tylko zapis „Chełm, woj. lubelskie” / „Chełm (woj. lubelskie)”
        if luka > 1 or not _bez_konca_zdania(tokeny, w.koniec, s.start):
            return False
        sep = tokeny[w.koniec].sep
        return "," in sep or "(" in sep
    return False


def _wybierz_kody(tokeny: list[Token], przyjete: list[_Przyjety]) -> list[_Przyjety]:
    """Zostawia przyjęte kody, z pominięciem szerszych, które są tylko doprecyzowane węższym miejscem.

    Szerszy kod (województwo lub powiat wskazane wprost) zostaje, gdy węższe miejsce jest osobną wzmianką
    (zasięg alertu się nie zawęża), także gdy to województwo pomogło rozstrzygnąć homonim w innym zdaniu.
    Kod poprzedzony „dla” (albo stojący w wyliczeniu zasięgu: „woj. X, miasto Y”) nigdy nie znika, także nad listą
    powiatów („dla woj. X - powiaty: A, B” daje `X`, A i B). Tak samo kod w nagłówku alertu (pierwsze zdanie, fraza
    przed dwukropkiem, tekst po prefiksie „Alert RCB”, „Ostrzeżenie”, „Komunikat”) i bez „dla”, także gdy dalej
    następuje „w powiecie…” albo „w gminie…”: nagłówek nie jest hierarchią jednego miejsca, o czym decyduje `_przylegle`.
    Znika tylko przy czystej hierarchii jednego miejsca (zob. `_przylegle`): lista powiatów pod województwem bez „dla”
    („części województwa: lubelskiego - powiaty: A, B”), dopisek województwa za listą lub nazwą („A (woj. X)”,
    „A, B (woj. X)”) albo zapis adresowy („w woj. X, w powiecie Y, w gminie Z”, „Z, woj. X”, „Z (pow. Y)”).
    Szerszy kod z miejsca jednostki lub ze spadku homonimu (nie wskazany wprost) znika zawsze, gdy w tekście
    jest węższe miejsce w nim zawarte.
    """
    wezsze: dict[str, list[_Przyjety]] = defaultdict(list)
    dopisek: set[str] = set()  # województwa dopisane za listą lub nazwą powiatu („A (woj. X)”): zawsze doprecyzowanie
    nad_lista: set[str] = set()  # województwa stojące przed listą powiatów jako jej nagłówek
    for q in przyjete:
        for d in (2, 4):
            if len(q.kod) > d:
                wezsze[q.kod[:d]].append(q)
        if q.h.typ == "pow" and q.h.zakres_doprecyzowuje:
            (nad_lista if q.h.zakres_z_naglowka else dopisek).update(z for z in q.h.zakres if q.kod.startswith(z))
    zostaja: list[_Przyjety] = []
    for idx, p in enumerate(przyjete):
        if len(p.kod) == 7 or p.kod not in wezsze:
            zostaja.append(p)
            continue
        if not p.zasieg or p.kod in dopisek:
            continue
        po_dla = _po_dla(tokeny, p.h.poczatek)  # „dla woj. X”: zasięg alertu, węższe miejsca go nie zastępują
        if p.kod in nad_lista:  # nagłówek listy powiatów („części województwa: lubelskiego - powiaty: A, B”): znika, chyba że po „dla”
            if po_dla:
                zostaja.append(p)
            continue
        if po_dla:
            zostaja.append(p)
            continue
        doprecyzowane = False
        for sasiad in range(idx + 1, len(przyjete)):  # sąsiedzi po pozycji: okno kilku tokenów, nie cały tekst
            q = przyjete[sasiad]
            if q.h.start - p.h.koniec > 4:
                break
            if q.kod.startswith(p.kod) and len(q.kod) > len(p.kod) and _przylegle(tokeny, p, q):
                doprecyzowane = True
                break
        if not doprecyzowane:
            for sasiad in range(idx - 1, -1, -1):
                q = przyjete[sasiad]
                if p.h.start - q.h.koniec > 4:
                    break
                if q.kod.startswith(p.kod) and len(q.kod) > len(p.kod) and _przylegle(tokeny, p, q):
                    doprecyzowane = True
                    break
        if not doprecyzowane:
            zostaja.append(p)
    return zostaja


def _pochodzenie(tokeny: list[Token], q: _Przyjety) -> bool:
    """Czy gmina oznacza miejsce pochodzenia wprost (bez dziedziczenia po liście): zob. `_role_pochodzenia`.

    Pochodzenie to tylko: (1) „z/ze + dopełniacz” w zasięgu 1-2 wyrazów od rzeczownika osobowego („Kierowca z
    Lublina”, „Strażacy z Lublina”, „Kierowca ciężarówki z Lublina”, „pochodzący z Lublina”); (2) rzeczownik
    „mieszkaniec/mieszkanka/kierowca/obywatel/rodak” i zaraz po nim dopełniacz („mieszkańca Lublina”). „z/ze” bez osoby,
    „od”, trasa i kierunek („Wiatr z Opola”, „10 km od Lubina”, „z A przez B do C”) to nie pochodzenie. Mianownik
    liczby mnogiej „mieszkańcy” oznacza dotkniętych zdarzeniem („Mieszkańcy Lublina bez prądu”), a „Dla mieszkańców
    gminy X” to adresat alertu: też nie.
    """
    if q.h.typ != "gmina":
        return False
    idx = q.h.poczatek if q.h.poczatek >= 0 else q.h.start
    if idx <= 0:
        return False
    poprzedni = tokeny[idx - 1].zlozony
    if poprzedni in ("z", "ze"):
        if tokeny[q.h.koniec - 1].tekst.lower().endswith(_NARZEDNIK):  # „z Tuchowem” (narzędnik) nie wskazuje pochodzenia
            return False
        for k in (idx - 2, idx - 3):  # rzeczownik osobowy w zasięgu 1-2 wyrazów przed „z”, w tym samym zdaniu
            if k < 0 or not _bez_konca_zdania(tokeny, k + 1, idx):
                break
            if tokeny[k].zlozony in _NIE_POCHODZENIE_MIANOWNIK:  # „Mieszkańcy z Krakowa i Warszawy bez prądu”: dotknięci
                return False
            if _OSOBA_Z.fullmatch(tokeny[k].zlozony) and not _po_dla(tokeny, k):
                return True
        return False
    return (poprzedni not in _NIE_POCHODZENIE_MIANOWNIK and _OSOBA_BEZPOSREDNIO.fullmatch(poprzedni) is not None
            and not _po_dla(tokeny, idx - 1))


def _dotkniety_mianownik(tokeny: list[Token], q: _Przyjety) -> bool:
    """Czy gmina stoi po „mieszkańcy z/ze” („Mieszkańcy z Krakowa i Warszawy bez prądu”): dotknięci zdarzeniem.

    Mianownik liczby mnogiej „mieszkańcy” z „z/ze” nie jest pochodzeniem; miejsce zostaje w wyniku, z uwagą
    `dotkniety-zdarzeniem` (zasięg nie jest zawężany: lepiej szerzej niż węziej).
    """
    if q.h.typ != "gmina":
        return False
    idx = q.h.poczatek if q.h.poczatek >= 0 else q.h.start
    if idx <= 0 or tokeny[idx - 1].zlozony not in ("z", "ze"):
        return False
    for k in (idx - 2, idx - 3):
        if k < 0 or not _bez_konca_zdania(tokeny, k + 1, idx):
            return False
        if tokeny[k].zlozony in _NIE_POCHODZENIE_MIANOWNIK:
            return True
    return False


def _kontynuuje_liste(tokeny: list[Token], poprzednie: _Przyjety, q: _Przyjety) -> bool:
    """Czy `q` jest kolejnym elementem listy zaczętej przez `poprzednie`: „Lublina, Świdnika i Chełma”.

    Elementy to nazwy rozdzielone przecinkiem, „i”, „oraz”, „lub”; nazwa nierozpoznana (wielką literą, do trzech
    wyrazów) w środku listy jej nie przerywa („Lublina, Janowa i Chełma”).
    """
    n = len(tokeny)
    cele = {q.h.start, q.h.poczatek}
    p = poprzednie.h.koniec
    for _ in range(_MAKS_ELEMENTOW_LISTY):
        if p >= n:
            return False
        k = _kontynuacja_listy(tokeny, p, tokeny[p].sep)
        if k is None:
            return False
        if k in cele:
            return True
        if not tokeny[k].wielka or tokeny[k].cyfra:
            return False
        p = k + 1
        while p < n and p - k < 3 and tokeny[p].wielka and not tokeny[p].cyfra and _SEP_PROSTY.fullmatch(tokeny[p].sep or ""):
            p += 1
    return False


def _role_pochodzenia(tokeny: list[Token], elementy: list[_Przyjety]) -> tuple[list[bool], list[int], list[bool]]:
    """Dla każdego miejsca: czy jest pochodzeniem, indeks pierwszego elementu jego listy i czy to dotknięci zdarzeniem.

    Element listy („A, B i C”, „A oraz B”) dziedziczy rolę pierwszego elementu: „Turyści z Zakopanego i Krakowa”
    to pochodzenie obu miast, „Mieszkańcy Lublina i Chełma” (dotknięci zdarzeniem) żadnego z nich, a „Mieszkańcy z
    Krakowa i Warszawy” to dotknięci zdarzeniem (nie pochodzenie). `elementy` zawiera też nazwy nierozstrzygnięte
    (`kod` pusty): przekazują rolę dalej („Kierowcy z Olsztyna i Elbląga”: nierozstrzygnięty Olsztyn jest głową listy).
    """
    pochodzi: list[bool] = []
    glowa: list[int] = []
    dotkniete: list[bool] = []
    for idx, q in enumerate(elementy):
        ciagnie = (idx > 0 and (pochodzi[idx - 1] or dotkniete[idx - 1]) and q.h.typ == "gmina" and elementy[idx - 1].h.typ == "gmina"
                   and _kontynuuje_liste(tokeny, elementy[idx - 1], q))
        dziedziczy = ciagnie and pochodzi[idx - 1]
        pochodzi.append(dziedziczy or _pochodzenie(tokeny, q))
        dotkniete.append((ciagnie and dotkniete[idx - 1]) or _dotkniety_mianownik(tokeny, q))
        glowa.append(glowa[idx - 1] if dziedziczy else idx)
    return pochodzi, glowa, dotkniete


def _slowo_trasy_za(tokeny: list[Token], koniec: int) -> bool:
    """Czy za nazwą (do `_OKNO_TRASY` wyrazów, to samo zdanie, przed spójnikiem „i”) stoi trasa: „do/po/przez” + nazwa.

    Słowo trasy to „do”, „przez” albo „po”, po którym stoi nazwa pisana wielką literą („od A po B”, „przez Kraków”);
    „po wypadku”, „do wieczora” i „przez śliską nawierzchnię” (rzeczownik pospolity: przyczyna) trasą nie są. Okno
    trasy otwiera słowo zaraz za nazwą („Lublina do Chełma”, „Krakowa przez Tarnów”) albo słowo ruchu między nazwą
    a słowem trasy („jechał dziś rano do Warszawy”, „trasa”, „droga”).
    """
    ruch = False
    for k in range(koniec, min(koniec + _OKNO_TRASY, len(tokeny))):
        if not _bez_konca_zdania(tokeny, k, k + 1):
            return False
        z = tokeny[k].zlozony
        if z in _KONIEC_OKNA_TRASY:
            return False
        if z in _SLOWA_TRASY:
            if (ruch or k == koniec) and k + 1 < len(tokeny) and tokeny[k + 1].wielka and not tokeny[k + 1].cyfra:
                return True
        elif z in _RUCH_WYRAZY or z.startswith(_RUCH_PREFIKSY):
            ruch = True
    return False


def _numery_zdan(tokeny: list[Token]) -> list[int]:
    numery, biezacy = [], 0
    for k, t in enumerate(tokeny):
        if k and t.poczatek_zdania:
            biezacy += 1
        numery.append(biezacy)
    return numery


@dataclass(slots=True)
class _Ciete:
    """Miejsce wycięte sporną heurystyką (rzeka, klub, kraina, imię) z rozstrzygnięciem, które by miało bez wycięcia."""

    h: _Trafienie
    r: _Rozstrzygniecie
    powod: str


def _pominiete(
    tokeny: list[Token], przyjete: list[_Przyjety], nierozstrzygniete: list[_Przyjety],
) -> tuple[dict[int, tuple[str, ...]], dict[int, tuple[str, ...]]]:
    """Przyjęte miejsca, które nie trafiają do wyniku: ({indeks w `przyjete`: uwagi do dopasowania}, {indeks: notatki}).

    * Miejsce jednostki (KMP, prokuratura, sąd, PSP) odpada, gdy obok stoi miejsce zdarzenia: „Policjanci z KMP
      w Płocku zatrzymali w gminie Słupno” to Słupno. Gdy jedynym miejscem jest jednostka („Policjanci z KPP
      w Garwolinie zatrzymali kierowcę”), zostaje (z niższą pewnością i uwagą `jednostka`).
    * Miejsce pochodzenia („mieszkańca Lublina”, „Kierowca z Lublina”, w tym cała lista „Turyści z Zakopanego i Krakowa”)
      odpada, gdy w tym samym zdaniu stoi miejsce jednostki lub zdarzenia: „Sąd Rejonowy w Chełmie skazał
      mieszkańca Lublina” to Chełm. Lista, za którą stoi trasa („do/po/przez” + nazwa w oknie 5 wyrazów, przed
      spójnikiem „i”: „Kierowca z Lublina do Chełma”, „jechał do Warszawy i miał wypadek w Płocku”), zostaje w całości.
      Gdy pochodzenie jest jedynym miejscem, zostaje.
    * „Mieszkańcy z Krakowa i Warszawy” (mianownik liczby mnogiej) to dotknięci zdarzeniem: miejsca zostają, a w
      dopasowaniach dostają uwagę `dotkniety-zdarzeniem` (drugi słownik wyniku).

    Pominięte miejsce zostaje w `dopasowania` z uwagami `poza-wynikiem` (oraz `pochodzenie`). `nierozstrzygniete` to
    nazwy bez rozstrzygnięcia: nie są miejscami wyniku, ale przekazują rolę kolejnym elementom listy.
    """
    wynik: dict[int, tuple[str, ...]] = {}
    notatki: dict[int, tuple[str, ...]] = {}
    elementy = sorted(
        [(q.h.start, 0, i, q) for i, q in enumerate(przyjete)] + [(q.h.start, 1, i, q) for i, q in enumerate(nierozstrzygniete)],
        key=lambda e: (e[0], e[1]))
    pochodzi, glowa, dotkniete = _role_pochodzenia(tokeny, [e[3] for e in elementy])
    pochodzenie_przyjetych = [False] * len(przyjete)
    for (_, nierozstrzygniety, i, _q), skad in zip(elementy, pochodzi):
        if not nierozstrzygniety:
            pochodzenie_przyjetych[i] = skad
    if any("jednostka" in q.uwagi for q in przyjete) and any(
            q.h.typ == "gmina" and "jednostka" not in q.uwagi and not skad for q, skad in zip(przyjete, pochodzenie_przyjetych)):
        for idx, q in enumerate(przyjete):
            if "jednostka" in q.uwagi:
                wynik[idx] = ("poza-wynikiem",)
    for (_, nierozstrzygniety, i, _q), dotkniety in zip(elementy, dotkniete):
        if dotkniety and not nierozstrzygniety:
            notatki[i] = ("dotkniety-zdarzeniem",)
    if any(pochodzi):
        zdania = _numery_zdan(tokeny)
        inne: dict[int, int] = defaultdict(int)  # zdanie: liczba miejsc, które nie są pochodzeniem
        trasa: set[int] = set()  # listy pochodzenia (indeks pierwszego elementu), za którymi stoi trasa
        for numer, ((_, nierozstrzygniety, i, q), skad) in enumerate(zip(elementy, pochodzi)):
            if skad:
                if _slowo_trasy_za(tokeny, q.h.koniec):
                    trasa.add(glowa[numer])
            elif not nierozstrzygniety:
                inne[zdania[q.h.start]] += 1
        for numer, ((_, nierozstrzygniety, i, q), skad) in enumerate(zip(elementy, pochodzi)):
            if skad and not nierozstrzygniety and inne[zdania[q.h.start]] and glowa[numer] not in trasa:
                wynik[i] = ("poza-wynikiem", "pochodzenie")
    return wynik, notatki


def _fraza_kraju_jest_zasiegiem(zlozony: str, poczatek: int) -> bool:
    """Odrzuca „z całej Polski”, „z całego kraju” oraz „najwięcej … w całym kraju”, niezależnie od czasownika."""
    przed = zlozony[:poczatek]
    if _PRZYIMEK_POCHODZENIA.search(przed):
        return False
    zdanie = max(przed.rfind(znak) for znak in _KONIEC_ZDANIA)
    return not _ILOSC_W_ZDANIU.search(przed[zdanie + 1:])


def _znajdz_kraj(zlozony: str) -> tuple[int, int] | None:
    """Pozycje frazy zasięgu krajowego w tekście (pozycje z tekstu złożonego jeden do jednego z oryginałem)."""
    najlepsze: tuple[int, int] | None = None
    for wzorzec in _WZORCE_KRAJU:
        for dopasowanie in wzorzec.finditer(zlozony):
            pozycje = dopasowanie.span(1)
            if _fraza_kraju_jest_zasiegiem(zlozony, pozycje[0]):
                if najlepsze is None or pozycje[0] < najlepsze[0]:
                    najlepsze = pozycje
                break
    return najlepsze


def _utnij(tekst: str) -> str:
    obciety = tekst[:MAKS_DLUGOSC]
    if tekst[MAKS_DLUGOSC].isalnum() and obciety[-1].isalnum():  # nie tnij wyrazu na pół
        ostatnia = max(obciety.rfind(" "), obciety.rfind("\n"))
        if ostatnia > MAKS_DLUGOSC - 100:
            obciety = obciety[:ostatnia]
    return obciety


def geokoduj(tekst: str | None) -> Wynik:
    """Rozpoznaje w tekście województwa, powiaty i gminy i zwraca ich kody TERYT.

    `teryt` ma kody 2-cyfrowe (województwo), 4-cyfrowe (powiat) i 7-cyfrowe (gmina);
    `dokladnosc` to najgrubszy z przyjętych poziomów (zasięg alertu, nie najmniejsze miejsce).
    Szczegóły każdego miejsca są w `dopasowania`. Tekst dłuższy niż `MAKS_DLUGOSC` jest obcinany (uwaga w wyniku).
    """
    if tekst is None:
        return Wynik((), BRAK, 0.0, ())
    if not isinstance(tekst, str):  # bytes, liczba, lista...: wynik `brak` z uwagą, nie wyjątek
        return Wynik((), BRAK, 0.0, (), ("zly-typ-wejscia",))
    if not tekst.strip():
        return Wynik((), BRAK, 0.0, ())
    uwagi_wyniku: tuple[str, ...] = ()
    if len(tekst) > MAKS_DLUGOSC:
        tekst, uwagi_wyniku = _utnij(tekst), ("obcieto-tekst",)
    tekst_wejsciowy = tekst
    tekst, mapa = normalizuj_wejscie(tekst)  # NFC i „Wroc­ławiu”: pozycje wyników wracają do oryginału przez `mapa`
    zlozony = zloz_pozycyjnie(tekst)
    tokeny = tokenizuj(tekst)
    wielkie = wyglada_na_wielkie_litery(tekst)
    trafienia, blokady = _szukaj_trafien(tokeny, wielkie, bool(_HYDROLOGIA.search(zlozony)))
    _przypisz_zakres_po(trafienia)

    wyniki: list[tuple[_Trafienie, _Rozstrzygniecie]] = []
    for h in trafienia:
        if h.typ in ("woj", "region"):
            wyniki.append((h, _rozstrzygnij_woj(h)))
    ctx_woj = {r.kody[0] for h, r in wyniki if r.kody}
    koniec_gmin = {h.koniec: h for h in trafienia if h.typ == "gmina"}  # koniec nazwy -> trafienie (dopisek powiatu)

    def gmina_przed_powiatem(h: _Trafienie) -> tuple[str, ...]:
        for k in range(h.start - 1, max(h.start - 4, 0), -1):
            gmina = koniec_gmin.get(k)
            if gmina is not None and _dopisek_powiatu(tokeny, k, h.start):
                return tuple(gmina.kody)
        return ()

    gminy_po_starcie = sorted((h for h in trafienia if h.typ == "gmina"), key=lambda g: g.poczatek if g.poczatek >= 0 else g.start)
    starty_gmin = [g.poczatek if g.poczatek >= 0 else g.start for g in gminy_po_starcie]

    def gmina_po_powiecie(h: _Trafienie) -> tuple[str, ...]:
        """Kody gminy wskazanej tuż za powiatem: „powiat opolski (gmina Poniatowa)”, „powiat X, w gminie Y”."""
        idx = bisect_left(starty_gmin, h.koniec)
        if idx >= len(gminy_po_starcie):
            return ()
        gmina, start = gminy_po_starcie[idx], starty_gmin[idx]
        if start - h.koniec > 1 or not _bez_konca_zdania(tokeny, h.koniec, start + 1) or not _bez_dwukropka(tokeny, h.koniec, start):
            return ()
        if not all(tokeny[k].zlozony in ("w", "we") for k in range(h.koniec, start)):
            return ()
        return tuple(gmina.kody)

    for h in trafienia:
        if h.typ == "pow":
            wieloznaczny = len(h.kody) > 1
            wyniki.append((h, _rozstrzygnij_powiat(
                h, ctx_woj, gmina_przed_powiatem(h) if wieloznaczny else (), gmina_po_powiecie(h) if wieloznaczny else ())))
    ctx_pow = {r.kody[0] for h, r in wyniki if r.kody and len(r.kody[0]) == 4}
    powiaty_w_tekscie = sorted(((h, r) for h, r in wyniki if h.typ == "pow" and r.kody), key=lambda para: para[0].start)
    starty_powiatow = [h.start for h, _ in powiaty_w_tekscie]

    woj_z_dopiskiem = {w.poczatek: w.kody[0][:2] for w in trafienia if w.typ == "woj" and w.tryb == "znacznik" and w.kody and w.poczatek >= 0}

    def woj_za_nazwa(h: _Trafienie) -> frozenset[str]:
        """Województwo dopisane tuż za nazwą: „Leszno (woj. mazowieckie)”, „Chełm, woj. lubelskie”."""
        kod = woj_z_dopiskiem.get(h.koniec)
        if kod and h.koniec < len(tokeny) and ("," in tokeny[h.koniec].sep or "(" in tokeny[h.koniec].sep):
            return frozenset({kod})
        return frozenset()

    def rozstrzygnij_gmine(h: _Trafienie) -> _Rozstrzygniecie:
        obok = _powiaty_za_nazwa(tokeny, h, starty_powiatow, powiaty_w_tekscie) if powiaty_w_tekscie else frozenset()
        return _rozstrzygnij_gmine(h, tokeny, ctx_pow, ctx_woj, obok, woj_za_nazwa(h))

    for h in trafienia:
        if h.typ == "gmina":
            wyniki.append((h, rozstrzygnij_gmine(h)))
    wyniki.sort(key=lambda para: para[0].start)
    # wyraźne miejsce z przyimkiem („w Warszawie”, „gmina X”): nazwa po imieniu, które bywa też gminą, wtedy odpada
    # (także powiat lub województwo po „w”: „Hanna Kraków zaginęła w powiecie pruszkowskim”)
    jest_miejsce_z_przyimkiem = any(
        r.kody and ((h.typ == "gmina" and not h.bez_przyimka and not h.po_imieniu)
                    or (h.typ in ("pow", "woj") and h.tryb in ("znacznik", "lista") and _w_przed(tokeny, h.poczatek)))
        for h, r in wyniki)

    dopasowania: list[Dopasowanie] = []
    przyjete: list[_Przyjety] = []
    ciete: list[_Ciete] = []  # miejsca wycięte heurystyką sporną (blokady, imię): do wyniku trafiają tylko jako uwaga
    nierozstrzygniete: list[_Przyjety] = []
    odrzucone = 0
    sprzeczne = any(r.sprzeczny for _, r in wyniki)
    # powiat wskazany wprost, ale nierozstrzygnięty (nazwa wieloznaczna: „powiat opolski”): zasięg alertu jest niepewny
    powiat_nierozstrzygniety = any(h.typ == "pow" and r.odrzucone for h, r in wyniki)
    sporne_powiaty = any(r.sporny for _, r in wyniki)
    for h, r in wyniki:
        fraza, start, koniec = _fraza(tekst_wejsciowy, tokeny, h, mapa)
        # nazwa bez przyimka: tylko miasto; wieś lub miasteczko („Kotła czarownic”) to nie miejsce zdarzenia (ślad zostaje)
        bez_miejsca = h.bez_przyimka and r.kody and len(r.kody[0]) == 7 and sl.jednostka(r.kody[0]).rodzaj != "miejska"
        if h.po_imieniu and jest_miejsce_z_przyimkiem and r.kody and not bez_miejsca:
            ciete.append(_Ciete(h, r, "imie"))  # „Hanna Kraków zaginęła w Warszawie”: Kraków to nazwisko (sporne)
            continue
        kody, uwagi = ((), r.uwagi + ("bez-przyimka",)) if bez_miejsca else (r.kody, r.uwagi)
        dopasowania.append(Dopasowanie(
            fraza=fraza, start=start, koniec=koniec, rodzaj=_rodzaj(h.typ), tryb=h.tryb, teryt=kody,
            dokladnosc=_dokladnosc(kody[0]) if kody else BRAK, pewnosc=round(r.pewnosc if kody else 0.0, 2),
            kandydaci=tuple(h.kody) if len(h.kody) > 1 else (), uwagi=uwagi))
        if bez_miejsca:
            continue
        if r.kody:
            przyjete.append(_Przyjety(r.kody[0], r.pewnosc, h, r.uwagi, len(dopasowania) - 1))
        else:
            if h.typ == "gmina":
                nierozstrzygniete.append(_Przyjety("", 0.0, h, r.uwagi))
            if h.tryb != "samodzielne":
                # nierozstrzygnięta nazwa ze znacznikiem („gmina Czernichów”) obniża pewność całego wyniku;
                # skrót lub homonim bez kontekstu („w Polsce”, „w Tomaszowie”) nie obniża pewności pozostałych miejsc
                odrzucone += 1
    for h in blokady:  # nazwy zablokowane przez rzekę, klub lub krainę: liczą się, gdy byłyby inaczej w wyniku
        r = rozstrzygnij_gmine(h)
        if r.kody and not (h.bez_przyimka and len(r.kody[0]) == 7 and sl.jednostka(r.kody[0]).rodzaj != "miejska"):
            ciete.append(_Ciete(h, r, h.blokada))
    pominiete, notatki = _pominiete(tokeny, przyjete, nierozstrzygniete)
    for idx, uwagi_pominiecia in {**{i: u for i, u in notatki.items()}, **pominiete}.items():  # ślad zostaje w `dopasowania`
        d = dopasowania[przyjete[idx].dopasowanie]
        dopasowania[przyjete[idx].dopasowanie] = replace(d, uwagi=d.uwagi + tuple(u for u in uwagi_pominiecia if u not in d.uwagi))
    wyciete = [(przyjete[idx].kod, przyjete[idx].pewnosc) for idx in pominiete]  # (kod, pewność) miejsc wyciętych z wyniku
    przyjete = [q for idx, q in enumerate(przyjete) if idx not in pominiete]

    zostaja = _wybierz_kody(tokeny, przyjete)
    kody = tuple(sorted({p.kod for p in zostaja}))
    zasieg_kraju = _znajdz_kraj(zlozony)
    sporne_ciecia = False
    if kody:
        # wycięte miejsce, które i tak jest w wyniku (z innej wzmianki), niczego nie zmienia: pewność zostaje
        for c in ciete:
            w_wyniku = c.r.kody[0] in kody
            if w_wyniku and c.h.blokada:  # blokada rzeki, klubu lub krainy, której miejsce jest w wyniku: bez śladu, jak dotąd
                continue
            fraza, start, koniec = _fraza(tekst_wejsciowy, tokeny, c.h, mapa)
            dopasowania.append(Dopasowanie(
                fraza=fraza, start=start, koniec=koniec, rodzaj=_rodzaj(c.h.typ), tryb=c.h.tryb, teryt=c.r.kody,
                dokladnosc=_dokladnosc(c.r.kody[0]), pewnosc=round(c.r.pewnosc, 2),
                kandydaci=tuple(c.h.kody) if len(c.h.kody) > 1 else (), uwagi=c.r.uwagi + ("poza-wynikiem", c.powod)))
            sporne_ciecia = sporne_ciecia or not w_wyniku
        wyciete = [(kod, pewnosc_miejsca) for kod, pewnosc_miejsca in wyciete if kod not in kody]
    if zasieg_kraju:
        start, koniec = _na_oryginal(mapa, *zasieg_kraju)
        dopasowania.append(Dopasowanie(
            fraza=tekst_wejsciowy[start:koniec], start=start, koniec=koniec, rodzaj=KRAJ, tryb=KRAJ,
            teryt=(), dokladnosc=KRAJ, pewnosc=PEWNOSC_KRAJ))
    dopasowania.sort(key=lambda d: d.start)
    dopasowania_krotka = tuple(dopasowania)

    if not kody:
        if zasieg_kraju:  # zasięg krajowy bez konkretnych miejsc
            return Wynik((), KRAJ, PEWNOSC_KRAJ, dopasowania_krotka, uwagi_wyniku)
        return Wynik((), BRAK, 0.0, dopasowania_krotka, uwagi_wyniku)
    pewnosc = min(p.pewnosc for p in zostaja)
    if wyciete or sporne_ciecia or sporne_powiaty:
        # zabezpieczenie strukturalne: wycięcie jednostki lub pochodzenia nie podnosi pewności (nie wyżej niż przed
        # wycięciem), a każde sporne wycięcie obniża ją do 0,75
        pewnosc = min([pewnosc, PEWNOSC_PO_WYCIECIU_MAX] + [pewnosc_miejsca for _, pewnosc_miejsca in wyciete])
    if sprzeczne:  # powiat z tekstu wykluczył nazwę: zostaje sam powiat, ale nie do publikacji automatycznej
        pewnosc = min(pewnosc, PEWNOSC_SPRZECZNY_KONTEKST)
    if odrzucone:  # zob. wyżej: tylko nazwy ze znacznikiem
        pewnosc *= WSPOLCZYNNIK_ODRZUCONEJ_NAZWY
    if powiat_nierozstrzygniety:  # reszta miejsc nie ukrywa, że część zasięgu jest nieznana: do przeglądu, nie do automatu
        pewnosc = min(pewnosc, PEWNOSC_PO_WYCIECIU_MAX)
    if zasieg_kraju:  # zasięg krajowy jest najgrubszy, ale nie zeruje konkretnych miejsc
        return Wynik(kody, KRAJ, round(min(pewnosc, PEWNOSC_KRAJ), 2), dopasowania_krotka, uwagi_wyniku)
    dokladnosc = min((_dokladnosc(k) for k in kody), key=lambda p: sl.DLUGOSC_KODU[p])
    return Wynik(kody, dokladnosc, round(pewnosc, 2), dopasowania_krotka, uwagi_wyniku)
