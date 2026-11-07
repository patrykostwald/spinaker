# spin.clinic: decyzje po audycie (9.10.2026)

Właściciel: „ufam ci, znasz kontekst całego projektu, wybierz to, co najlepsze”. Poniżej decyzje Claude do audytu `docs/AUDYT_SPIN_CLINIC_PO_SPINKACH.md` (sekcja G). Każdą można zmienić jednym zdaniem właściciela.

1. **Wycięcie dwuetapowe.** Najpierw ukrycie (THREADS_ENABLED=false, kod zostaje, sygnały i zadania Celery odpięte), eksport danych i tag `spinki-freeze`. Migracje usuwające tabele dopiero po eksporcie i po kilku tygodniach spokojnej pracy bez spinek. Powód: odwracalność przy minimalnym koszcie.
2. **Spinki Dr. Spina znikają razem z czytelniczymi.** Nową główną jest strona w układzie Kliniki: przekazy dnia (rząd i opozycja), najnowsze diagnozy, wywiad dnia, wskaźniki, wzmianka o aplikacji i newsletter. Tak mówi nowy kierunek (zostają diagnozy, przekazy i wywiady).
3. **Liczby z bazy produkcyjnej:** właściciel uruchamia zapytania tylko do odczytu (COUNT) z listy w sekcji „Komendy”; wyniki trafiają do archiwum.
4. **Alerty:** cel opóźnienia: mediana do 3 minut, 95 percentyl do 10 minut od publikacji wpisu. Budżet na X na start 5 USD miesięcznie (jak dziś), podnoszony razem z przychodami z alertów (próg: pierwszy płacący klient). Dopuszczamy inne źródła: oficjalne strony i kanały RSS partii oraz instytucji, YouTube (kanały oficjalne), komunikaty Sejmu. Dopasowanie po identyfikatorach, bez scrapingu.
5. **Cisza nocna:** ustawienie użytkownika; domyślnie 23:00-07:00 wyłączone powiadomienia, z opcją „budź mnie” dla wybranych osób.
6. **Stary model `news.Thread` i `/thread/[slug]`:** ukryć (bez usuwania kodu); decyzja o usunięciu po wdrożeniu nowej głównej. Zachować możliwość użycia w ofercie dla redakcji jako przykładu.
7. **Sygnały lobbingu i nowe narracje:** nie kasować; przenieść do raportów B2B (Raportysta) jako materiał źródłowy.
8. **Komentowanie:** wymagamy potwierdzonego e-maila (jak dziś); dodajemy logowanie przez Google i Apple (Apple i tak będzie potrzebne w aplikacji w sklepie); włączamy publiczne liczniki trafne/nietrafne po poprawie designu; dodajemy komentarze pod przekazami dnia (zmiana ograniczenia w bazie).
9. **Moderacja:** filtr AI plus przegląd człowieka (właściciel lub wyznaczona osoba); cel reakcji na zgłoszenie: 24 godziny; apelacja od decyzji dodana w etapie komentarzy. Konieczne do regulaminu usługi hostingowej (patrz pytania do prawnika).
10. **Aplikacja:** pod marką spin.clinic, ta sama baza kont; start jako PWA, sklepy po ustalonym progu aktywnych użytkowników (np. 500 tygodniowo) i po osobnej zgodzie właściciela (punkt APP-01 w PLAN_AKTUALNY.md).

## Komendy (właściciel, na serwerze, tylko odczyt)
Zapytanie zliczające (pokazuje tylko liczby): polecenie `manage.py shell -c` z listą modeli spinek i powiązań; dokładną komendę dostarcza zlecenie 108 (eksport), która ma tryb `--tylko-liczby`.

## Kolejność prac
1. Zlecenie 108: polecenie eksportu spinek do plików (tylko odczyt) i tryb liczb.
2. Design nowej powłoki i głównej: prompt dla Projektanta (plik `PROMPT-DO-PROJEKTANTA-spin-clinic-glowna.md` w `Desktop\projekty\spin-clinic-gotowe\`), pętla panelu designu, zrzuty 1440 i 390, `odstepy.js`.
3. Wycięcie (odpiąć sygnały i zadania, flaga false, usunąć trasy i komponenty, przekierowania, teksty prawne).
4. Komentowanie, 5. alerty, 6. PWA, 7. raporty i oferta.
