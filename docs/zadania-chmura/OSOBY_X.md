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
