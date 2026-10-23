# Raport: konta X osób publicznych (gałąź `cloud/osoby-x`, 23.10)

## Dlaczego osoby bez konta X omijały diagnozy
1. **Złe dowody ze stron partii** (28 odrzuceń 22.10). `party_leads` dla osoby brało wszystkie linki X ze strony głównej
   partii, bo pole `party_handle` było puste: posłowie KO dostawali @Platforma_org, Arkadiusz Sikora - @__Lewica i konta
   innych polityków z listy na stronie Lewicy, Włodzimierz Skalik - @KoronyPolskiej. Każdy taki link to płatny odczyt X
   i blokada „konto powiązano z innym profilem”.
2. **Profile Sejmu nie dają się pobrać** (sejm.gov.pl: HTTP 403, nie obchodzimy). Dla posłów jedynym źródłem była
   Wikidata dopasowana po nazwisku, a ona odpadała przy dwóch kontach albo przy imienniku.
3. **Kolejka „Do decyzji”**: zmiana obozu, brak obozu, konto niepotwierdzone, dowód odrzucony - wszystko czekało na człowieka.
4. **Obóz**: kluby spoza listy obozów blokowały czytanie. W danych X kadencji to 25 posłów: Centrum 14, niezrzeszeni 7,
   Demokracja 4. **Marek Jakubiak** ma w danych klub „RozwojPlus”, który już był przypisany do opozycji - u niego obóz nie
   blokował; wypadł przez punkty 1-2 (budżet odczytów zjadany przez złe linki, brak źródła dla posłów poza nazwiskiem).
5. **Błędy „źródło niedostępne”** (30 razy): kod nie zapisywał, które źródło padło. W tym etapie wyjątki sieciowe rzuca
   praktycznie tylko wyszukiwarka (Groq); profile Sejmu, Senatu i strony partii łapały błędy po cichu. Od teraz raport
   podaje nazwę źródła i typ błędu.

## Co zmieniono
- **Linki**: konto partii, klubu i instytucji nigdy nie jest kontem osoby (lista `NON_PERSON_HANDLES`). Ze strony partii
  i z wyszukiwarki tylko konto z nazwiskiem osoby; z oficjalnego profilu z kilkoma kontami - tak samo. Odrzucone linki
  nie kosztują odczytu X. Konto czytane już przy innej osobie: bez odczytu, a przy mocnym dowodzie - konflikt.
  Uwaga: „blok profilu osoby” jest przybliżony dopasowaniem nazwiska (HTML stron jest różny); konto bez nazwiska w
  nazwie (np. @Henryk55957871) przejdzie tylko jako jedyny link na profilu osoby albo z Wikidata/osoby_x.csv.
- **Nowe źródło dokładne** (pierwsze w kolejności): `news/data/osoby_x.csv` (oficjalne strony) i Wikidata P2002 po
  identyfikatorze PE (P1186) albo profilu posła (P973), co noc. Osoby z takim dowodem idą pierwsze - nowy poseł,
  minister czy europoseł dostaje konto tej samej nocy (w granicach dziennego limitu odczytów).
- **Automatyczne włączenie**: mocny dowód (Wikidata po identyfikatorze, osoby_x.csv, link na oficjalnym profilu) nie
  czeka na zgodność nazwy wyświetlanej; twarde warunki zostają (nazwisko w koncie, parodia, konto młodsze niż 6 mies.).
- **Obóz „inni i niezrzeszeni”** (`other`): klub spoza listy albo brak klubu u osoby z rejestru. Konto jest czytane
  i diagnozowane (diagnozy pojedynczych wpisów), ale nie wchodzi do przekazów dnia, które porównują dwa obozy.
- **Drugi klucz zamiast człowieka**: zmiana obozu idzie za oficjalnym składem (klub z Sejmu/Senatu/PE; tylko na obóz
  z listy klubów - „inni” nigdy nie nadpisuje obozu ustawionego wcześniej), konto
  wyłączone po dwóch zgodnych odczytach nie wraca do kolejki, dowód odrzucony przez Strażnika jest sprawdzany ponownie,
  nigdy nie czytane konto z kolejki włącza mocny dowód tej samej tożsamości (to samo ID X). Do człowieka trafia tylko
  konflikt dowodów: w panelu, w mailu Strażnika i przez `account_warden.conflicts_for_report()` dla porannego
  raportu Korektora - z gotową propozycją.
- **Flaga Drugiego klucza**: rejestr agentów traktował brak `WARDEN_SECOND_KEY_ENABLED` jako „wyłączony”, a kod jako
  „włączony”. Teraz oba: brak flagi = włączony.
- **Pokrycie**: `manage.py osoby_x_pokrycie` pokazuje też, ile osób czeka, od kiedy, kolejkę Strażnika i koszt.
- **Rzadsze czytanie**: konto bez wpisów przez 30 dni czytane co 6 godzin.
- „Redakcja/redaktor” zamienione na „zespół” / „do weryfikacji” w modelach kont (migracja 0170 zmienia tylko etykiety
  i dodaje obóz `other`).

## Koszt (pkt 5 dopisku)
Na konto miesięcznie: średnia wpisów na konto dziennie x 30 x 0,005 USD + kontrola profilu co 7 dni (ok. 0,043 USD).
Przy 2 wpisach dziennie to ok. 0,34 USD na konto, czyli ok. 34 USD za 100 nowych kont. Prawdziwą średnią z produkcji
liczy `manage.py osoby_x_pokrycie` („Gdyby wszystkie brakujące osoby dostały konto: ...”), a raport Strażnika po każdym
przebiegu („przewidywany wzrost kosztu X”). Twardy limit zostaje: `X_POLITICAL_MONTHLY_USD_LIMIT` (domyślnie 5 USD) -
przy przekroczeniu Strażnik wydłuża interwały czytania, więc **przy nowych kontach trzeba podnieść limit**, inaczej
wszystkie konta będą czytane rzadziej.

## Czego nie zrobiono
- Wiceministrowie: w kodzie nie ma automatycznej synchronizacji kierownictw ministerstw (lista 24.09 była ręczna).
  Propozycja: komenda czytająca strony „Kierownictwo” na gov.pl, jak `sync_kprp_leadership`.
- Senatorowie w Wikidata: nie znam pewnego identyfikatora Senatu w Wikidata, więc senatorowie są dopasowywani po
  nazwisku (jednoznacznie) i przez profile senat.gov.pl jak dotąd.
- Ta sesja nie miała dostępu do Wikidata, więc `osoby_x.csv` ma tylko 78 kont z oficjalnych stron; resztę dociąga
  serwer (komendy niżej).
