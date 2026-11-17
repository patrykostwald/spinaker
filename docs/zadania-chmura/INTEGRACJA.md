# Zadanie: scalenie nocnych gałęzi i poprawki P0 (gałąź `cloud/integracja-2310`)

Przeczytaj `docs/zadania-chmura/WSPOLNE.md`.

1. Utwórz `cloud/integracja-2310` z `origin/cloud/baza-2310`, scal kolejno `origin/cloud/osoby-x`, `origin/cloud/korektor`,
   `origin/cloud/przeszlosc-rozwoj`. Konflikty rozwiąż z sensem (pliki zadań w `docs/zadania-chmura/` bierz z baza-2310 +
   raporty z gałęzi). Obie gałęzie mają migrację `0170` (`0170_konta_oboz_inni_zespol`, `0170_krs_kolejka`): przenumeruj
   jedną na `0171` z zależnością od drugiej; `makemigrations --check` bez zmian.
2. Podłącz `account_warden.conflicts_for_report()` do porannego raportu Korektora (obie gałęzie zostawiły to sobie nawzajem).
3. Napraw P0 z `docs/SLEDCZY_RUNDA_3.md`: P0-11 („Wpływy” liczone z wartości całego ogłoszenia TED przy wielu wykonawcach -
   nazwij i licz uczciwie, poza sumą, gdy nie wiadomo, ile dostał podmiot), P0-12 (furtka `grounded` w agencie KRS - źródło
   potwierdza tylko, gdy przeczytana strona wymienia osobę i podmiot), P0-13 (Stan danych liczy też głosowania, oświadczenia,
   RCL, wpisy X; bez twierdzenia „Brak znanych braków” bez pokrycia). Oraz P1 z tej rundy: kolejka KRS (podmioty bez NIP w
   odpisie nie wracają co noc z priorytetem 0), „NIP bez KRS” poprawnie nazwany, ucinane opisy na telefonie, odmiana liczebników.
4. `scraper/catalog.py`: konto `sjnowacka` podpisane „Szymon Hołownia” - sprawdź w Wikidata/oficjalnym źródle, czyje to konto,
   popraw podpis; przejrzyj całą listę TWITTER_POLITICIANS tak samo.
5. Cały zestaw testów `news` i `scraper` (znany wcześniej błąd `test_spina_v3.py::test_rejected_step_rules` - sprawdź, czy da się
   naprawić bez zmiany zachowania; jeśli nie, opisz). Potem niezależna recenzja kodu całości (agent recenzent, inny niż autor)
   i poprawki.
6. `docs/zadania-chmura/WDROZENIE_2310.md`: kolejność wdrożenia (migracje, zmienne środowiskowe z wartościami domyślnymi,
   restart, pierwsze komendy kontrolne: `korektor --dni 7`, `osoby_x_pokrycie`, raport pokrycia KRS, stan danych), co
   sprawdzić po wdrożeniu i jak się wycofać. Uwaga: na produkcji `X_POLITICAL_MONTHLY_USD_LIMIT` jest ustawione na 100 USD
   (w październiku wydane ok. 80 USD) - nie zmieniaj domyślnej wartości w kodzie, podaj tylko przewidywany koszt nowych kont.

Celuj w ok. 2 godziny.
