# Zadanie: Korektor - ostry recenzent faktów (gałąź `cloud/korektor`)

Przeczytaj `docs/zadania-chmura/WSPOLNE.md`.

## Dlaczego
Właściciel znalazł wpadki, które nie mogą się powtarzać:
1. Na spin.clinic przy wywiadzie z prezydentem Karolem Nawrockim w jednym miejscu podpisano go jako „Andrzej Duda”
   (prezydentem od 6.08.2025 jest Karol Nawrocki; Andrzej Duda to były prezydent). Modele językowe mają stare wiadomości.
2. Na przeszłość.today Marek Jakubiak nie ma przypiętego konta X, choć je ma.
3. Na przeszłość.today nie wszędzie są dane z KRS i innych źródeł (puste sekcje profili).

## Co zbudować
1. **Rejestr urzędów** `backend/news/urzedy.py`: aktualni (stan 23.10.2026) prezydent, premier, marszałkowie Sejmu i Senatu,
   ministrowie, szefowie klubów i partii - każdy wpis ze źródłem (link do oficjalnej strony) i datą objęcia; plus lista
   „byłych” (np. Andrzej Duda - prezydent 2015-2025). Każdą pozycję zweryfikuj wyszukiwaniem; niepewne `[DP]` i pomiń w regułach.
2. **Wstrzyknięcie faktów do promptów**: wszędzie, gdzie model pisze o osobach (wywiad dnia `clinic_interview.py`, diagnozy
   `clinic.py`, przekaz dnia, karty X, opisy osób przeszłości) dodaj krótki blok „Aktualne urzędy na dzień <data>” z rejestru.
3. **Strażnik spójności** `backend/news/korektor.py` + komenda `manage.py korektor [--dni N] [--napraw]`:
   - nazwa osoby vs urząd (np. „prezydent Andrzej Duda” w tekście po 6.08.2025, gość wywiadu niezgodny z tytułem/kanałem filmu,
     ta sama osoba różnie podpisana na jednej stronie), sprawdzane na treściach z ostatnich N dni;
   - osoby publiczne bez konta X tam, gdzie konto jest w rejestrze/zweryfikowanej liście (zobacz też gałąź `cloud/osoby-x`
     - nie duplikuj jej pracy, tylko czytaj plik `backend/news/data/osoby_x.csv`, jeśli istnieje);
   - profile przeszłości z pustymi sekcjami (KRS, oświadczenia, głosowania, zamówienia) - liczby i lista;
   - `--napraw` robi tylko bezpieczne rzeczy: poprawia metadane (gość wywiadu), odrzuca i zleca ponowne wygenerowanie treści
     z błędem urzędu (bez edycji treści), przypina konta X z listy zweryfikowanej; reszta trafia do raportu dla koordynatora.
   - raport mailem na adres z `LOOP_REPORT_EMAIL` (istniejący mechanizm maili pętli), rano po nocnych zadaniach; wpis w
     harmonogramie tak jak inne nocne komendy (znajdź, jak są planowane, np. celery beat).
4. **Bramka przed publikacją**: nowa treść z błędem urzędu nie może się opublikować automatycznie (wstrzymaj, oznacz, zleć
   ponowne wygenerowanie). Dodaj to w miejscu, gdzie treści są zatwierdzane.
5. Test regresyjny na przypadek „wywiad z prezydentem Nawrockim podpisany jako Andrzej Duda” i na inne zamiany osób.
6. Wpis pętli w LOOPS / Automatyka (znajdź w kodzie, jak opisane są inne pętle i ich opiekunowie) - opiekun: Korektor.

Znajdź też w kodzie, skąd mógł się wziąć podpis „Andrzej Duda” (np. `scraper/catalog.py` TWITTER_POLITICIANS, mapowanie
urzędu na konto, prompt, transkrypcja) i napraw przyczynę, nie tylko objaw. Opisz przyczynę w raporcie.

Celuj w ok. 2-3 godziny.
