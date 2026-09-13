# spin.clinic — pakiet przekazania dla kolejnego asystenta AI

Stan: 14 września 2026. Ten dokument nie zawiera sekretów i może zostać otwarty przez asystenta przeglądarkowego.

## Materiały wejściowe

- Repozytorium: https://github.com/patrykostwald/spinaker
- Gałąź robocza: `codex/plan-2026-09-13`
- Aktualny plan: `PLAN_AKTUALNY.md`
- Audyt istniejącego Supabase: `docs/SUPABASE_AUDIT_2026-09-14.md`
- Instrukcja aplikacji lokalnej: `README_APP.md`
- Projekt Supabase: `yyrwcggmksjhzeaovrvl`, publiczny adres projektu: `https://yyrwcggmksjhzeaovrvl.supabase.co`

Nie proś właściciela o wklejenie hasła bazy, klucza `service_role`, klucza API ani pliku `.env` do rozmowy. Nie umieszczaj sekretów w kodzie, odpowiedzi ani repozytorium. Asystent przeglądarkowy bez osobnej autoryzacji ma przygotowywać analizę lub patch, a nie zakładać, że ma prawo zapisywać GitHub albo Supabase.

## Niezmienne decyzje produktu

1. Jeden Box to jeden materiał źródłowy: artykuł, reportaż, wywiad, film, podcast, post, komunikat, dokument, akt prawny, głosowanie, orzeczenie, reklama lub inny jawnie oznaczony typ.
2. Box publiczny pokazuje przede wszystkim tytuł, źródło, datę, miniaturę, typ i link do oryginału. Obecność materiału nie potwierdza jego twierdzeń.
3. Nitka odwołuje się do Boxów i nie kopiuje ich treści.
4. Rzetelność obejmuje jawne braki, datę i metodę pozyskania, historię zmian oraz oddzielenie danych źródłowych, klasyfikacji automatycznej i komentarzy użytkowników.
5. Użytkownik może mieć jedną reakcję i jeden komentarz na Box. Widoczność aktywności na profilu kontroluje użytkownik.
6. Wysyłanie próśb do wydawców zawsze wymaga zatwierdzenia właściciela. Problemy techniczne i prawne trafiają do kolejki administratora.
7. MVP korzysta z wymiennego adaptera AI. Dane, źródła, reguły i wyniki ewaluacji pozostają przenośne; nie zakładamy przeniesienia pamięci ani wag usługowego modelu.

## Potwierdzony stan techniczny

- Lokalny Django/SQLite: 314 źródeł, 117 828 materiałów, 3 563 664 zadań archiwalnych, 111 327 rekordów `ArticleContent`.
- Supabase: 601 źródeł, 0 Boxów. Schemat aplikacyjny istnieje, ale przed zapisem wymaga migracji bezpieczeństwa opisanej w audycie.
- Lokalny harvester metadanych działa z czterema wykonawcami. Nowe pełne teksty są domyślnie wyłączone przez `ARCHIVE_STORE_FULL_TEXT=false`.
- Backend: 416 testów zaliczonych. Oba frontendy Next.js budują się poprawnie.

## Najbliższy zakres pracy

1. Zaproponuj mapowanie lokalnego `Article` do Supabase `boxes` bez wykonywania migracji i bez sekretów.
2. Zdefiniuj kontrakt rekordu pośredniego harvester → walidator → Supabase, w tym identyfikator źródła, kanonikalny URL, precyzję daty, typ materiału, miniaturę, wynik polityki i pochodzenie.
3. Wypisz przypadki deduplikacji i błędów. Ten sam URL ma być idempotentny; podobny tytuł nie wystarcza do scalenia.
4. Przygotuj testy kontraktu na fikcyjnych domenach. Nie uruchamiaj masowego pobierania.
5. Zgłoś rozbieżności z `PLAN_AKTUALNY.md`; nie zmieniaj samodzielnie decyzji produktu.

## Kandydat na dostawcę AI

DeepSeek V4 Flash/Pro jest kandydatem ze względu na API zgodne z formatem OpenAI Responses, duży kontekst i niski deklarowany koszt. Nie jest jeszcze wybranym dostawcą. Przed integracją trzeba porównać jakość na naszym zamkniętym zestawie testowym, limit kosztu, stabilność JSON/tool calls, warunki użycia, retencję i miejsce przetwarzania danych. Do pilota można wysyłać wyłącznie publiczne metadane źródeł; komentarze, dane kont i inne dane użytkowników pozostają wyłączone do czasu analizy prywatności i zawarcia wymaganych umów.
