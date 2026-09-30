# Zlecenie 052 — Audytor-inkwizytor

## Działanie

Audytor pracuje bez AI, o pełnej godzinie od 7 do 23 (Europe/Warsaw). Czyta dzisiejsze diagnozy, zapisane opinie, `CouncilSeat` i nowe pomiary `CouncilCall`. Panel pokazuje przepustowość i jakość oddzielnie dla koalicji i opozycji, globalny cel `paced_target`, pozostały budżet, czas od ostatniej diagnozy oraz 12 ostatnich wyników zadania diagnoz. Historyczne wpisy bez czasu odpowiedzi pozostają bez pomiaru — nie są zerami.

Automatycznie, z dziennikiem `RepairAction` (`auditor:*`):

- Po co najmniej trzech kolejnych dzisiejszych błędach 402/429/timeout odkłada model na ławkę do lokalnej północy. Cache z datą jest czytany przez `_members`; następnego dnia model wraca bez zmiany `CouncilSeat`.
- Ustawia kolejność zapasowych w rolach według dzisiejszego odsetka sukcesów. Nie dodaje i nie usuwa członków.
- Gdy świeża kolejka zalega względem celu, jest budżet i działa AI, zleca najwyżej jeden dodatkowy `clinic_diagnose_task` na godzinę. Normalny worker nadal egzekwuje swoje limity, tempo i blokadę.
- `failures_today()` zlicza tylko rozpoznane błędy trwałe. Brak kworum, 429, timeouty, połączenia, 5xx i limity dzienne nie uruchamiają całodziennego stopu.

Audytor nie edytuje diagnoz, nie podnosi budżetów, nie doładowuje portfeli, nie zmienia kluczy ani składu. Duża różnica udziału spinów (30 punktów procentowych) lub średniej siły (20 punktów) przy n<20 w którymkolwiek obozie daje ostrzeżenie z oboma n, bez orzekania stronniczości.

## Inkwizytor i równa miara

Beat uruchamia kontrolę o 21:45. Wspólna blokada zapobiega równoległemu wydawaniu limitów przez diagnozy i kontrole; zajęta blokada powoduje ograniczone ponowienia zadania. Naprawiacz rozpoznaje blokadę inkwizytora i nie zwalnia jej na podstawie pulsu zwykłych diagnoz.

Przed 21:00 komenda odmawia kontroli przy nieobsłużonej świeżej kolejce. Losowanie obejmuje opublikowane diagnozy z ostatnich 48 godzin, bez powtórek, z równoważeniem obozów także między kilkoma wywołaniami tego samego dnia. Nieparzyste miejsce jest losowe. Brak drugiego obozu nie jest uzupełniany wymyślonym materiałem.

Każdą diagnozę sprawdzają dwa różne modele dwóch znanych firm, żaden nie jest jej przewodniczącym. Oba dostają identyczny materiał, źródła z zapisanych twierdzeń, skalę, Kartę i pięć zamkniętych kryteriów. Brak odpowiedzi lub niepoprawny JSON daje wątpliwość. Błąd łączny wymaga dwóch poprawnych odpowiedzi z werdyktem błąd. Sprzeczne odpowiedzi zamknięte nie ustanawiają błędu.

Domyślny twardy limit to **3 rozpoczęte kontrole dziennie** (`INQUISITOR_DAILY`). `--limit` może go tylko ograniczyć. Rezerwacja w bazie jest przed wywołaniami; awaria lub restart procesu nie zwraca wykorzystanego miejsca. Blokada transakcyjna chroni limit również po utracie cache. Czas przebiegu jest ograniczony. Długie materiały, których wywołanie nie przyjęłoby w całości, oraz diagnozy bez rozpoznanego przewodniczącego są pomijane.

Kontrole korzystają wyłącznie z istniejących darmowych ścieżek Groq/NIM i modeli OpenRouter `:free`, przez zwykłe `ask()` i `registry.reserve()`. Nie ma płatnego zapasu. Gemini pozostaje dostępne dla diagnoz, ale nie dla dodatkowych kontroli.

Treść i status diagnozy domyślnie pozostają nietknięte. Przy dwóch błędach kontrola trafia do listy „Do decyzji właściciela”. Link prowadzi do nieedytowalnego przeglądu z przyciskami zatwierdź/odrzuć i linkiem do oryginalnej diagnozy. Opcja `INQUISITOR_AUTO_HIDE=true` pozwala wyłącznie wtedy przenieść opublikowaną diagnozę do `pending_review`; domyślnie jest wyłączona. Decyzja i autor decyzji są zapisywani osobno.

Panel oraz raport tygodniowy pokazują liczbę kontroli i powtarzające się zarzuty per obóz oraz model uczestniczący w ocenianych diagnozach. Uczestnictwo nie stanowi dowodu winy konkretnego modelu. Te same diagnozy mogą być ujęte przy kilku członkach; tych liczników nie należy sumować jako liczby różnych diagnoz.

## Wspólne powiadomienia

Rozszerzono istniejący mail naprawiacza, z tym samym wyborem adresu właściciela i `_mail`. Każde zgłoszenie zawiera: co się stało, wykonaną automatykę i następne działanie.

- Pilne: 3 godziny bez diagnozy przy kolejce, 2 godziny bez nowych wpisów X w dzień, 2 godziny bez minimalnego kworum, brak środków oraz jednomyślny błąd inkwizytora.
- Braki środków są zgłaszane już przy odpowiedzi dostawcy, również gdy późniejszy zapas ukrył awarię. Warunki czasowe sprawdza naprawiacz co 15 minut i audytor co godzinę.
- Ten sam problem: najwyżej jeden pilny mail na 6 godzin, trwała rezerwacja przed SMTP. Pozostałe nowe zdarzenia trafiają do jednego maila w godzinie 8:00.
- „Rozwiązane” tylko po wcześniejszym skutecznym zgłoszeniu pilnym. Dla portfela wymagany jest rzeczywisty sukces zapytania; upływ czasu ani błąd 429 nie dowodzą doładowania. Noc nie rozwiązuje zastoju.
- W dzienniku działań i mailu są kody/stałe opisy, nigdy wyjątki, tokeny ani surowe odpowiedzi API. Uzasadnienia AI pozostają w chronionym przeglądzie, nie w mailu.

## Wdrożenie i sprawdzenie

Przed uruchomieniem nowych workerów/beat należy zastosować migrację `0096_council_auditor_inquisitor` zwykłym `python manage.py migrate`. W tej kopii migrację tylko utworzono i sprawdzono na testowej bazie; nie wdrażano produkcji i nie zmieniano `.env`.

Komendy kontrolne z `backend`:

```text
python manage.py council_audit --dry-run
python manage.py inquisitor --dry-run --limit 3
```

Dry-run nie wywołuje modeli, nie zapisuje bazy/cache i nie wysyła maila. Powiadomienia wymagają istniejącej konfiguracji SMTP/adresu właściciela; produkcyjne blokady współdzielone wymagają istniejącego Redis.

Weryfikacja w tej kopii: **211 testów przeszło** (`test_council_auditor`, `test_repairer`, `test_council_expansion`, `test_council_recruiter`, `test_clinic`, `test_political_intake`, `test_admin_status`, `test_admin_finance`). Modele mockowane, `.env` nieodczytywane. `npx --no-install tsc --noEmit -p .` w `frontend-spin` zakończone kodem 0. `makemigrations --check --dry-run`: brak niezapisanych zmian modeli. `git diff --check`: bez błędów. Pozostały istniejące ostrzeżenia Django o domyślnym schemacie URL i testowym braku katalogu `staticfiles`.

## Zmienione pliki

- Nowe: `backend/news/council_health.py`, `council_auditor.py`, `inquisitor.py`, `test_council_auditor.py`, komendy `management/commands/council_audit.py` i `inquisitor.py`, migracja `migrations/0096_council_auditor_inquisitor.py`, szablon `templates/admin/news/inquisitor_review.html`.
- Potok/model/panel: `backend/news/clinic.py`, `clinic_ai.py`, `clinic_council.py`, `clinic_models.py`, `clinic_admin.py`, `political_polling.py`, `repairer.py`, `tasks.py`, `admin_status.py`, `test_admin_status.py`, `weekly_report.py`, `backend/config/celery.py`.
- UI: `packages/ui/src/components/CommandPanel.tsx`, `components/clinic/WeeklyReport.tsx`, `lib/clinicReports.ts`.
- Raport: `deploy/auditor-inquisitor-052.md`. Izolacja testów bez odczytu `.env`: lokalny pomocnik w `.pytest-tmp/052-noenv`, poza kodem produkcyjnym.

## Ograniczenia

Kontrola jest próbką, nie dowodem bezstronności całej puli. Brak dwóch niezależnych darmowych recenzentów oznacza mniej kontroli, bez płatnego zapasu. Małe próby są ujawnione. Godzinny audyt nie przyspieszy zewnętrznego dostawcy ani nie usunie ograniczeń budżetu; wyczerpane portfele i konfiguracja nadal wymagają właściciela. Niepełne kontrole po awarii procesu są zachowane bez ponownego wydawania limitu. Pomiary `CouncilCall` narastają w bazie; zadanie nie wprowadza usuwania danych.
