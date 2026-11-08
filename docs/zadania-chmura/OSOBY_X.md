# Zadanie: konta X osób publicznych (gałąź `cloud/osoby-x`)

Przeczytaj `docs/zadania-chmura/WSPOLNE.md`.

## Problem
Osoby publiczne na spin.clinic i przeszłość.today nie mają przypiętych kont X (przykład właściciela: Marek Jakubiak).
Istnieją już: pole konta X na źródle (`news/models.py`, `x_handle`), `source_social.py`, `x_link_cards.py`, komendy
`import_public_figure_x_csv`, `x_accounts_export`, plik `backend/tmp/x_kandydatury_osoby_publiczne_2026-09-24.csv`,
`scraper/catalog.py` (TWITTER_POLITICIANS, stara lista ok. 40 kont), `news/data/sejm_career.json` (posłowie).
Najpierw zrozum, jak osoba publiczna jest łączona z kontem X na obu stronach, i dlaczego Jakubiak wypadł.

## Co zrobić
1. Lista wszystkich osób publicznych, które mamy w danych (posłowie obecnej i poprzedniej kadencji z `sejm_career.json`,
   senatorowie, europosłowie, ministrowie, prezydent, liderzy partii) -> dla każdej oficjalne konto X ze źródłem.
   Źródła w kolejności: Wikidata (właściwość P2002 „X username”, przez SPARQL query.wikidata.org - legalne, CC0), oficjalna
   strona osoby/partii/Sejmu linkująca do konta, profil zweryfikowany wymieniony na gov.pl. Bez skrobania X.com.
   Konto bez źródła = nie wpisuj. Konta byłe/zawieszone oznacz.
2. Wynik: `backend/news/data/osoby_x.csv` (imię i nazwisko, identyfikator osoby w naszych danych, konto, źródło, data
   sprawdzenia, pewność) i rozszerzenie `import_public_figure_x_csv`, żeby importowała ten plik idempotentnie na produkcji.
3. Napraw przyczynę braku (np. dopasowanie nazwisk z polskimi znakami, osoby spoza starej listy) i dodaj test na Jakubiaka.
4. Zaktualizuj `scraper/catalog.py`, jeśli przypisuje role nieaktualnie (np. „prezydent” = @AndrzejDuda; prezydentem od
   6.08.2025 jest Karol Nawrocki) - konto Andrzeja Dudy zostaje, ale jako były prezydent.
5. Komenda kontrolna `manage.py osoby_x_pokrycie`: ile osób ma konto, ile nie, lista braków. Podaj wynik dla danych w repo.

Celuj w ok. 2 godziny.

## Dopisek 23.10 (właściciel: „bez konta X osoba omija diagnozy - to idiotyczne”)
Mechanizm już istnieje: `news/account_warden.py` (Strażnik kont, nocny), `link_official_x_accounts` (senat.gov.pl, PE,
Wikidata P2002), `warden_second_key.py` (Drugi klucz, flaga WARDEN_SECOND_KEY_ENABLED), modele w `news/political_models.py`.
Problem jest w tym, że niejasne przypadki lądują w „Do decyzji” (`pending`: brak jednoznacznego obozu, zasięg < 500, opis
bez funkcji, inna nazwa) i nikt ich nie rozstrzyga, więc osoba nie jest czytana i nie ma diagnoz.
Napraw to systemowo, w duchu „najpierw automatyczna naprawa”:
1. Konto potwierdzone oficjalnym źródłem (Wikidata P2002 z dopasowaniem po identyfikatorze Sejmu/Senatu/PE, link na oficjalnym
   profilu) włącza się automatycznie, bez czekania na człowieka.
2. Brak jednoznacznego obozu nie blokuje czytania: obóz „inne / niezrzeszeni”, z wyjaśnieniem w raporcie (np. koła, posłowie
   niezrzeszeni - tak może być z Markiem Jakubiakiem; sprawdź na danych).
3. Kolejka „Do decyzji” rozstrzygana automatycznie przez Drugi klucz (drugie, niezależne sprawdzenie), a do człowieka trafia
   tylko prawdziwy konflikt dowodów - w porannym raporcie Korektora, z gotową propozycją.
4. Nocna synchronizacja składu: nowi posłowie, ministrowie, wiceministrowie, europosłowie, liderzy - konto X dopinane w tej
   samej nocy. Komenda pokrycia ma pokazywać także „ile osób czeka i od kiedy”.
5. Koszt: każde nowe czytane konto to wydatek w budżecie X (`X_POLITICAL_MONTHLY_USD_LIMIT`). Policz przewidywany wzrost
   miesięcznego kosztu i zapisz w raporcie; częstotliwość czytania kont o małej aktywności rzadsza (mechanizm `interval` istnieje).

## Dane z produkcji 23.10 (Strażnik kont, przebieg 22.10)
177 kont czytanych, 3 wyłączone, 19 kandydatów nierozstrzygniętych; Jakubiaka nie ma ani wśród kont, ani wśród kandydatów
(odkrywanie go pominęło). WARDEN_SECOND_KEY_ENABLED nieustawione (Drugi klucz wyłączony).
Przebieg 22.10: 51 odrzuceń, 30 błędów „źródło niedostępne; ponowienie później”, 1 do decyzji. Odrzucenia:
- 28 x „Konto powiązano już z innym profilem; do decyzji.” - dowody są złe: posłom przypisywane są konta partii i innych osób
  (Tomasz Głogowski, Krystyna Sibińska, Rafał Siemaszko, Tomasz Siemoniak -> @Platforma_org; Arkadiusz Sikora -> @__Lewica,
  @wlodekczarzasty, @AgaBak, @KGawkowski, @KotulaKat, @MarcinKulasek; Włodzimierz Skalik -> @koronypolskiej). Parser bierze
  wszystkie linki X ze strony (stopka, lista klubu), a nie konto tej osoby. Napraw: link przyjmowany tylko, gdy jest w bloku
  profilu osoby i nazwa/handle pasuje do osoby; konta partii i klubów nigdy jako konto osoby; test na tych przypadkach.
- 17 x „zmiana obozu do decyzji.”, 5 x „Istniejące konto jest wyłączone lub niepotwierdzone”, 1 x „Dowód odrzucony wcześniej”
  - rozstrzygać automatycznie (Drugi klucz), do człowieka tylko konflikt.
- 30 błędów źródła: ustal, które źródło (np. sejm.gov.pl 403, senat, Wikidata) i dodaj obejście legalne (Wikidata/API Sejmu
  api.sejm.gov.pl zamiast stron profili).
Słowo „redakcja” nie opisuje naszego zespołu - w tekstach i nazwach używaj „zespół” albo „do weryfikacji”.
