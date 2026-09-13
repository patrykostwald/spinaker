# Audyt Supabase — 14 września 2026

Projekt: `spin-clinic-mvp`, region `eu-central-1`, stan `ACTIVE_HEALTHY`.

## Stan danych

- `sources`: 601 rekordów.
- `boxes` i `box_versions`: 0 rekordów.
- tabele encji, tagów, cytatów, nitek, profili, reakcji i komentarzy: 0 rekordów.
- Jedyna zarejestrowana migracja: `20260913201856_extend_sources_with_priority_and_legal_fields`.

Schemat zawiera właściwe ograniczenia unikalności dla jednego głosu i jednego komentarza użytkownika na Box oraz analogicznie dla nitki. `boxes` ma unikalność `(source_id, url)`. Przed ingestem trzeba ustalić kanonikalizację adresów, ponieważ ten sam materiał może występować pod różnymi URL.

## Blokery przed zapisem harvesterów

1. Funkcje `handle_new_user` i `set_latest_version` nie mają bezpiecznie ustawionego `search_path`.
2. Funkcje `handle_new_user` i `rls_auto_enable` są `SECURITY DEFINER` i według doradcy są wykonywalne przez role publiczne. Należy odebrać niepotrzebne uprawnienia i nadać tylko jawnie wymagane.
3. Polityki RLS używają bezpośredniego `auth.uid()`; doradca zaleca `(select auth.uid())` dla stabilnego planu zapytania.
4. Brakuje indeksów dla dziesięciu kluczy obcych, m.in. autorów komentarzy/głosów oraz relacji Box–tag/encja/nitka.
5. Publiczne tabele nie mają obecnie bezpośrednich grantów `anon` ani `authenticated`. Przed uruchomieniem klienta trzeba jawnie zdecydować, które tabele wystawia Data API, i dopiero potem nadać minimalne uprawnienia wraz z RLS.

Nie zastosowano zmian w produkcji. Migrację bezpieczeństwa należy przygotować, przejrzeć na wyższym poziomie effortu, wykonać jako nazwaną migrację i ponownie uruchomić doradców bezpieczeństwa oraz wydajności.

## Rozbieżność z lokalnym portalem

Lokalny Django używa własnych modeli `Source`, `Article`, `ArchiveJob` i `ArticleContent`. Lokalna baza zawiera 314 źródeł, 117 828 materiałów, 3 563 664 zadań archiwalnych i 111 327 rekordów treści. Supabase używa modelu `sources`/`boxes` i nie zawiera jeszcze materiałów. Nie wolno podłączać obu systemów przez proste kopiowanie tabel.

Potrzebny jest jawny adapter:

1. lokalny harvester pobiera i normalizuje metadane,
2. zapisuje wynik w kolejce pośredniej z identyfikatorem źródła Supabase,
3. walidator sprawdza URL, datę, typ, politykę źródła i kompletność,
4. dopiero zatwierdzony rekord trafia do `boxes`,
5. pełna treść i dowody dostępu pozostają oddzielone od publicznego Boxa i respektują politykę źródła.

Do czasu wdrożenia adaptera import może bezpiecznie pracować lokalnie, ale nie należy przedstawiać go jako zawartości produkcyjnego Supabase.
