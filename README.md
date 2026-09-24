# spin.clinic

Repozytorium projektu: portal Next.js, backend Django, importery źródeł oraz dokumentacja. Kod został dołączony do osobnej gałęzi roboczej po skanowaniu sekretów; lokalna baza SQLite, pliki środowiskowe, logi, zależności i zbudowane artefakty pozostają poza repozytorium.

## Aktualny plan

Zacznij od [PLAN_AKTUALNY.md](PLAN_AKTUALNY.md): trzy etapy rozwoju, Supabase, kontrola uprawnień, harvestery i współpraca Codex/Claude.

`plan_pelny.md` jest materiałem wejściowym użytkownika. `project.md`, `roadmap.md` i `infrastructure.md` zachowują starsze założenia; ich terminy, ceny i ustawienia nie są potwierdzeniem bieżącego wdrożenia. `sources.md` wymaga uzgodnienia z nowym katalogiem Supabase.

## Stan integracji

- Lokalny portal i wcześniejsze harvestery są zachowane w katalogach `frontend-spin`, `backend` i `packages`.
- Aktualny zakres produktu opisuje [PLAN_AKTUALNY.md](PLAN_AKTUALNY.md).
- Odczyt istniejącego Supabase i wykryte blokery opisuje [audyt Supabase](docs/SUPABASE_AUDIT_2026-09-14.md).
- Nie uruchamiać starszych instrukcji migracji i importu bez sprawdzenia zgodności ze schematem Supabase.

Ta gałąź nie zmienia automatycznie bazy Supabase ani środowiska publicznego.
