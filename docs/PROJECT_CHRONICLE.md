# Kronika powstawania spin.clinic

Ten dokument jest trwałym dziennikiem projektu przygotowywanym z myślą o przyszłej książce. Zapisuje decyzje, przełomy, błędy, wyniki eksperymentów i podział pracy między człowieka oraz narzędzia AI. Nie przechowuje kluczy, haseł, prywatnych danych ani pełnych treści źródeł.

## Początek idei

spin.clinic powstało z potrzeby pokazania kontekstu przed oceną treści — `CONTEXT BEFORE CONTENT`. Podstawową jednostką został box: jedno źródło, niezależnie od tego, czy jest artykułem, dokumentem, filmem, wypowiedzią, postem, reklamą czy wzmianką. Boxy łączą się w chronologiczne nitki, dzięki którym użytkownik może zobaczyć rozwój wydarzenia zamiast pojedynczego nagłówka.

Nazwa i język produktu świadomie nawiązują do kliniki: Dr Spin analizuje twierdzenia, Izba przyjęć przyjmuje materiały społeczności, a role redakcyjne mogą używać nazw Ordynator i Doktor. Ustalono jednak, że marka ma pozostać profesjonalna i powściągliwa, bez rozbudowanego znaku medycznego — podstawowym logo jest napis `spin.clinic`.

## Najważniejsze decyzje produktowe

- MVP zaczyna się od bogatego archiwum legalnie dostępnych źródeł, strony głównej z paskami wiadomości, TOP 10, tematu dnia, Dr Spina i nitek zatwierdzonych autorów.
- Zwykli użytkownicy w MVP mogą personalizować źródła i hasła, zapisywać nitki, komentować oraz reagować. Publiczne nitki społeczności należą do etapu drugiego.
- Wklejenie publicznego URL najpierw uruchamia wyszukiwanie kontekstu w bazie i dozwolonych źródłach. Osobny przycisk Dr Spin analizuje sprawdzalne twierdzenia według jawnych kategorii metodologicznych.
- Wynik Dr Spina jest analizą z dowodami, zakresem pokrycia, niepewnością i historią korekt. Nie jest certyfikatem prawdy.
- W MVP publiczne analizy zatwierdza redakcja. Automatyzacja może rosnąć dopiero po pomiarze jakości i odsetka korekt.
- Oficjalne API X ma objąć bieżące posty ręcznie zweryfikowanej listy polityków oraz instytucji. Obóz polityczny jest informacją redakcyjną, a nie inferencją modelu.
- Płatne modele AI są wymienne. Ich wejścia, wyniki, wersje promptów, koszty i korekty budują audytowalny zbiór ewaluacyjny dla przyszłego własnego modelu.
- Trzy motywy produktu to: ciemny główny, jasny oraz pastelowy „Polska droga”. Typografia łączy IBM Plex Sans, Serif i Mono.

## 14 września 2026 — pierwsza noc skalowania

- Lokalne archiwum osiągnęło ponad 155 tysięcy boxów, a kolejka kandydackich URL przekroczyła 3,8 miliona pozycji.
- Uruchomiono ograniczony czasowo backfill: konfiguracja do 32 workerów, najwyżej jedno aktywne pobranie na domenę i minimum trzy sekundy odstępu, zwiększane przez reguły wydawcy.
- Audyt map OKO.press wykrył, że indeks obejmował także tagi, osoby i instytucje. Pobieranie zatrzymano, błędne zadania poddano kwarantannie, a importer ograniczono do map postów. Ten incydent potwierdził, że liczba URL nie może zastępować kontroli jakości boxów.
- Audyt praw i dostępu rozdzielono od audytu technicznego. Publiczna mapa strony nie jest automatycznie zgodą na masowe pobieranie. Źródła blokujące odpowiednie klasy botów trafiają na listę próśb o dostęp lub współpracę.
- Claude Code połączono z projektem przez lokalną kolejkę tekstową i osobny worktree. Pierwsze zbyt szerokie zadania wyczerpały limit kroków; po uproszczeniu procesu Claude ukończył opt-in mechanizm prywatnych snapshotów dowodowych.
- Snapshoty przechowują prywatny artefakt poza bazą, a w bazie jedynie metadane, hash, podstawę zgody, wersję parsera i retencję. Funkcja pozostaje domyślnie wyłączona i odmawia zapisu bez jawnego statusu prawnego.
- Mistral EU został podłączony przez adapter, lecz pierwsza minimalna próba API zwróciła HTTP 429. Dalsze próby zatrzymano, aby nie generować kosztów ani szumu.
- Powstał lokalny monitor pokazujący tempo tworzenia boxów, stan kolejki, błędy, źródła, pracę Claude’a i najważniejsze zdarzenia AI. Komputer zabezpieczono przed uśpieniem na dziesięć godzin.
- Trzy warianty wizualne wyeksportowano w rozdzielczości 1600 × 1050. Zachowano tekstowe logo i osadzone lokalnie fonty.
- Podczas przygotowania materiałów przed snem okazało się, że wcześniejsze, zaakceptowane wizualizacje z ilustracyjną „polską drogą” nie zostały zachowane jako trwałe pliki. Zamiast nich powstała techniczna rekonstrukcja, która nie odpowiadała wspólnym ustaleniom. Błąd wykrył właściciel projektu; serię odtworzono, a samo zdarzenie stało się argumentem za zapisywaniem nie tylko decyzji, lecz również ich wizualnych artefaktów, wersji i pochodzenia.
- Ustalono, że Codex i Claude mają prowadzić krótkie, zrozumiałe dla człowieka zapisy ważnych decyzji, przełomów, nieudanych prób oraz napraw. Dziennik ma pokazywać rzeczywisty proces współpracy człowieka z różnymi systemami AI, bez upiększania historii i bez sekretów.

## Zasada dalszego zapisu

Kronika opisuje wydarzenia językiem zrozumiałym dla przyszłego czytelnika: co się wydarzyło, dlaczego miało znaczenie, kto lub które narzędzie uczestniczyło oraz jaki był wynik. Szczegółowe telemetrie pozostają w logach operacyjnych. Każdy wpis pomija sekrety i dane prywatne.
