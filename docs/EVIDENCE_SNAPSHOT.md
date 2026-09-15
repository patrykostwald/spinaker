# Prywatny snapshot dowodowy boxa

Mechanizm domyślnie wyłączony (`EVIDENCE_SNAPSHOT_ENABLED=False`). Nic w repozytorium nie wywołuje go automatycznie — nie ma zaplanowanego zadania ani masowego pobierania obrazów/screenshotów. To wewnętrzne, redakcyjne narzędzie dowodowe, przygotowane pod przyszły OCR i weryfikację, nie funkcja publiczna.

## Co to jest i czym nie jest

`EvidenceSnapshot` (`backend/news/evidence_snapshot.py`) to metadane jednego prywatnie przechowanego artefaktu dowodowego powiązanego z boxem (`Article`). To **nie to samo** co:

- publiczna miniatura `Article.image_url` — jawna, pokazywana w interfejsie, pochodzi z metadanych wydawcy (`meta:og:image`/`meta:twitter:image`);
- `ArticleContent` — publiczny/redakcyjny wyciąg tekstu artykułu z hashem odpowiedzi.

Snapshot dowodowy jest odrębny i nigdy nie jest serializowany do publicznego API ani wyświetlany czytelnikowi. Traktuj go jak `QualityIssue`/`AIResearchCall` — widoczny tylko w panelu redakcyjnym.

## Co zapisuje rekord

| Pole | Znaczenie |
|---|---|
| `article` | ID boxa, którego dotyczy dowód |
| `fetch_attempt` | niezmienny identyfikator udanej próby pobrania, z której pochodzi artefakt |
| `source_url` | adres, z którego pobrano artefakt |
| `fetched_at` | czas pobrania |
| `content_sha256` | hash SHA-256 treści/obrazu (nie same bajty) |
| `artifact_type` | `html` / `image` / `pdf` / `other` |
| `parser_version` | wersja parsera, który wyprodukował artefakt |
| `consent_status` | `unknown` / `allowed` / `restricted` / `denied` — stan zgody/licencji wydawcy |
| `storage_key` | klucz do prywatnego backendu storage, wyznaczony z hasha treści |
| `retention_policy` + `retention_expires_at` | polityka retencji i (opcjonalnie) data wygaśnięcia |

**Baza nigdy nie przechowuje sekretów ani binariów.** Same bajty artefaktu (HTML, obraz, PDF) trafiają wyłącznie do backendu storage, nigdy do wiersza w bazie.

## Interfejs storage

`backend/news/snapshot_storage.py` definiuje abstrakcyjny interfejs `SnapshotStorage` (`put`/`get`/`exists`/`delete`) oraz `LocalFileSnapshotStorage` — backend testowy/deweloperski zapisujący pod `backend/media/evidence_snapshots/` (katalog już objęty `.gitignore`, nie jest ścieżką publiczną/statyczną). `get_snapshot_storage()` zwraca ten backend domyślnie; przed użyciem produkcyjnym podmień go na prywatny, niepubliczny backend (nie na produkcyjny Supabase — ten projekt trzyma katalog źródeł i publiczne boxy w Supabase, dowody prywatne są celowo poza nim).

`put()` jest idempotentny dla identycznej treści (ten sam klucz + te same bajty nie tworzy duplikatu) i odmawia nadpisania istniejącego klucza inną treścią — klucze są wyznaczane z hasha treści, więc niezgodność sygnalizuje błąd wywołującego kodu.

## Zgoda i pobieranie

`capture_snapshot()` (`backend/news/evidence_snapshot.py`) to jedyny sposób utworzenia nowego rekordu:

- rzuca `EvidenceSnapshotDisabled`, dopóki `settings.EVIDENCE_SNAPSHOT_ENABLED` nie jest jawnie ustawione;
- odmawia zapisu dla `consent_status='unknown'` i `consent_status='denied'`; wywołujący musi jawnie przekazać `allowed` albo `restricted` zgodnie z decyzją dla źródła;
- nie pobiera niczego samodzielnie — wywołujący dostarcza już pobrane `content`; brak masowego pobierania obrazów czy screenshotów w tym repozytorium.
- wymaga udanej, audytowanej `FetchAttempt` tego samego źródła. Nie można stworzyć nowego snapshotu z materiału, którego pobrania system nie potrafi wskazać.

## Migracja

`news/migrations/0028_evidencesnapshot.py` utworzyła tabelę `news_evidencesnapshot`; migracja `0046` chroni teraz box i powiązaną próbę pobrania przed usunięciem, gdy istnieje snapshot. Starsze rekordy mogą nie mieć `fetch_attempt`, ale wszystkie nowe snapshoty go wymagają. Brak dodatkowych ograniczeń unikalności na `storage_key`: ta sama treść obserwowana ponownie może współdzielić klucz storage z wcześniejszym wpisem, ale każda obserwacja zostaje osobnym, datowanym wierszem.

## Panel redakcyjny

`EvidenceSnapshotAdmin` (`backend/news/admin.py`) jest tylko do odczytu poza `consent_status`, `retention_policy` i `retention_expires_at` — redakcja może zmienić stan zgody i retencję, ale nie może utworzyć wiersza ręcznie (taki wiersz miałby metadane bez odpowiadającego artefaktu w storage).

## Przyszły OCR

Snapshoty `image`/`pdf` są przygotowane pod przyszłe OCR: `parser_version` pozwoli odróżnić wynik kolejnych wersji ekstrakcji tekstu z tego samego artefaktu, a `content_sha256` pozwoli sprawdzić, czy artefakt się nie zmienił, zanim OCR zostanie ponownie uruchomiony. OCR nie jest zaimplementowany w tym zadaniu — to tylko przygotowanie miejsca na wynik.
