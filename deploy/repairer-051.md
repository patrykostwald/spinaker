# Podręcznik naprawiacza (051)

Naprawiacz czyta `admin_status.snapshot(now)`, używany także przez panel.
Wykonuje co najwyżej 20 działań na przebieg (łącznie z zapisanymi pominięciami,
błędami i mailem). Blokada przebiegu trwa 600 s, zadanie Celery ma twardy timeout
240 s; po 180 s kod nie rozpoczyna kolejnych napraw. Błąd reguły nie przerywa
pozostałych. Przełączniki i instalacja strażnika są opisane w [README](README.md).

| Reguła | Mechanizm i uzasadnienie |
| --- | --- |
| Zadania | Tylko alarmy z sekcji zadań panelu: puls `error` lub ponad 2× maksymalny odstęp harmonogramu, z uwzględnieniem nocy i weekendów. `send_task` bierze nazwę, args, kwargs i opcje z beat. Świadomie wyłączonych zadań nie ponawia. Puls `running` wymaga dodatkowo przekroczenia zarejestrowanego twardego timeoutu; bez znanego timeoutu ponowienie jest pomijane. |
| Limity zadań | Jedna próba na 60 min, trzy w ruchomych 24 h; wspólne także dla kilku wpisów beat uruchamiających to samo zadanie z tymi samymi argumentami. Próba trafia do bazy przed wysłaniem do brokera; niejednoznaczny błąd wysyłki też zużywa limit. |
| Blokady | Jawny katalog kluczy z `tasks.py` i ich twardych timeoutów. Wszystkie powiązane pulsy muszą być zakończone i starsze niż timeout. Redis usuwa klucz przez Lua porównujące jednocześnie blokadę i pulsy; LocMem używa własnego mutexu. Nieznany backend cache nie usuwa blokad. |
| Pobrania | Rezerwacje starsze niż godzinę zamyka istniejący `reap_incomplete_fetches`, z selekcją pojedynczego request_id. Powstaje fakt `abandoned`, zachowane są blokady wierszy i istniejące zawieszanie instrukcji po trzech porzuconych pobraniach. Domyślny próg samego reapera (5 min) pozostaje bez zmian. |
| Diagnozy | Tylko `failed`, ostatnie 48 h, bez ukrytych wpisów. `queue_for_diagnosis` zmienia wyłącznie status; `repair_attempts` ogranicza liczbę powrotów do dwóch, niezależnie od retencji dziennika. Dzienne limity dostawców czekają do następnego dnia. Zwykły worker nadal pilnuje czasu pracy i budżetów. |
| Archiwa | Tylko `failed`, aktywne źródło, liczba prób poniżej `MAX_ARCHIVE_ATTEMPTS=5`, `available_at` już minęło i błąd jest przejściowy. Powrót do `pending` zachowuje licznik oraz termin. Partia najwyżej 50 ponowień; globalny limit pozwala zmienić najwyżej 20. Obecny worker sam ponawia `error`; kwarantanna nie jest ruszana. |
| Importery | Przejściowy `last_error`, brak sukcesu przez ponad 2× rytm, jawne mapowanie ImportState na beat. Współdzielą limit z regułą zadań. Nieznane mapowanie trafia do właściciela. |
| Wywiad | Najnowszy materiał z panelu, `failed`, błąd przejściowy, bez ukrycia, tylko przy `clinic_interview.enabled()`. Istniejące `queue_interview` przy zachowaniu autora i dnia; najwyżej jeden powrót, z blokadą wiersza. Brak bezpośrednich wywołań modeli. |
| Właściciel | Portfele, środki, klucze, konfiguracja, zasoby VPS i niezweryfikowane zadania. Mail od 8:00 Europe/Warsaw, raz dziennie; brak maila bez nowych problemów. Stan dnia i odciski problemów są w bazie, nie w ulotnym cache. Konsylium 429 nie powoduje żadnej naprawy ani maila. |
| Dziennik | `RepairAction`: czas, reguła, cel, wynik, bezpieczny opis. Wyjątki przechodzą przez `safe_error`; puls zachowuje tylko klasyfikację błędu. Powtarzający się identyczny problem właściciela jest zapisywany najwyżej raz na 24 h. Retencja 30 dni obejmuje wyłącznie dziennik. |

## Audyt dopuszczonych zadań

Lista `SAFE_TASKS` jest zamknięta — nowe zadania wymagają przeglądu kodu.
Obejmuje importy oficjalne/RSS/NewsAPI/GDELT, odkrywanie i pobieranie archiwów,
kontrolę dostępu i jakości metadanych oraz urzędowe listy osób i karierę sejmową.
Adaptery nadal sprawdzają dostęp, flagi, dzierżawy i limity pobrań.
NewsAPI rezerwuje dzienny budżet w `reserve_budget` przed zapytaniem.
YouTube używa transakcyjnej rezerwacji dziennych jednostek w `youtube_collect`.
Sprawdzanie usuniętych postów używa darmowego oEmbed, a odkrywanie linków
społecznościowych nie odpytuje płatnego API X.
Strażnik Kliniki używa darmowych Groq/NIM. Diagnozy postów przechodzą przez
`run_diagnoses` z oknem dziennym, pacingiem, limitem błędów i rezerwą budżetu USD.

Nie ponawiamy automatycznie publikacji X/social, Dr. Spin Threads, Rekrutera,
agenta KRS, raportu tygodniowego, wyboru wywiadu, przekazów dnia ani pollingu X:
efekty zewnętrzne lub bezpieczeństwo kosztów wymagają osobnego potwierdzenia.
Przetwarzanie wywiadu wraca wyłącznie przez ograniczoną regułę pojedynczego
rekordu, bez ogólnego ponawiania tego zadania z beat.

Nie poprawiamy treści AI, nie usuwamy artykułów, diagnoz ani wpisów. Nie zmieniamy
kluczy, konfiguracji, `.env`, portfeli ani składu Konsylium. Trwałe 4xx poza 429,
niepoprawne treści, odrzucenia i brak klucza wykluczają ponowienia. Dysk/RAM
pozostają decyzją właściciela; osobny watchdog ma tylko wskazane dwa polecenia prune.

## Ograniczenia wdrożeniowe

- Najpierw migracja 0095, następnie nowy backend, worker i beat. Panel korzysta
  z istniejących kart; nie wymaga zmiany TypeScript ani CSS.
- Produkcja wymaga współdzielonego Redis (jak obecne ustawienia). LocMem służy
  testom i pojedynczemu procesowi, nie koordynuje wielu workerów.
- Wysłanie do brokera/SMTP i zapis w SQL nie są jedną transakcją. Rezerwacja próby
  przed wysłaniem zapobiega duplikatom; awaria w tym miejscu może opóźnić kolejną
  próbę. Nieudany mail jest ponawiany dopiero następnego dnia.
- Nieznany/trwały błąd nie jest zgadywany jako przejściowy. Brak pulsu nie daje
  dowodu osierocenia blokady. Dziennik nie zastępuje monitoringu poza aplikacją.
- Nowe testy używają atrap brokera, SMTP i poleceń Docker/HTTP; weryfikują także
  atomowe porównanie dla Redis, ale nie uruchamiają rzeczywistego Redis/systemd.
- Watchdog korzysta z istniejącego `/api/health/` (baza i cache); sprawdza partycję
  `/srv/spin-clinic`. Jego instalacja na VPS pozostaje oddzielnym krokiem wdrożenia.

## Pliki zmienione w zleceniu

- `backend/news/repairer.py` — reguły, limity, dziennik, mail i karta panelu.
- `backend/news/models.py`, `backend/news/clinic_models.py`,
  `backend/news/migrations/0095_repairer.py` — dziennik, stan naprawiacza i liczniki ponowień.
- `backend/news/admin_status.py` — wspólny snapshot i nowa sekcja.
- `backend/news/task_heartbeat.py` — bezpieczna klasyfikacja trwałych błędów.
- `backend/news/tasks.py`, `backend/config/celery.py`,
  `backend/news/management/commands/repairer.py` — zadanie, beat i komenda JSON.
- `backend/scraper/fetch_reaper.py` — opcjonalny wybór request_id i limit,
  bez zmiany dotychczasowego zachowania.
- `backend/news/test_repairer.py`, `backend/news/test_admin_status.py` — nowe testy
  i dostosowanie liczby sekcji panelu z 18 do 19.
- `deploy/watchdog.sh`, `deploy/spin-watchdog.service`, `deploy/spin-watchdog.timer`,
  `deploy/.gitattributes` — strażnik hosta, jednostki i końce linii LF.
- `deploy/README.md`, `deploy/repairer-051.md` — instalacja i niniejszy podręcznik.
