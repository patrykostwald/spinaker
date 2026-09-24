# Rozstrzygnięcie dziewięciu kart roboczych — 16 września 2026

## Metoda

Każda decyzja jest zawężona do konkretnego kanału i endpointu. `READY_TO_RUN`
oznacza wyłącznie zatwierdzony, audytowany adapter metadanych; nie uprawnia do
pobierania plików, treści stron ani innych endpointów. `READY_TO_CONTACT`
utworzyło kartę kontaktową gotową do kontroli, lecz nie wysyła wiadomości.

| Źródło | Decyzja | Zakres i dowód | Stan wykonania |
| --- | --- | --- | --- |
| dane.gov.pl | READY_TO_RUN | `GET https://api.dane.gov.pl/1.4/datasets`, wyłącznie indeks metadanych; [dokumentacja](https://api.dane.gov.pl/doc) | Karta API v2; preflight 2026-09-16: poprawny JSON, 47 721 B. Bez zasobów i plików. |
| GUS BDL (`stat.gov.pl`) | READY_TO_RUN | `GET https://bdl.stat.gov.pl/api/v1/subjects?lang=pl&format=json`, wyłącznie lista tematów; [dokumentacja i CC BY 4.0](https://api.stat.gov.pl/home/bdlapi) | Karta API v2; preflight 2026-09-16: poprawny JSON, 1 830 B. Bez danych liczbowych i innych endpointów. |
| UOKiK aktualności | READY_TO_CONTACT | [katalog RSS](https://uokik.gov.pl/public/rss) | Brak potwierdzonego ścisłego feedu dla tej sekcji i warunków; karta kontaktowa v2. |
| Kancelaria Prezydenta RP | READY_TO_CONTACT | [ponowne wykorzystanie](https://www.prezydent.pl/kancelaria/ponowne-wykorzystywanie-informacji-sektora-publicznego) | Zasady dotyczą BIP; brak zweryfikowanego kanału wiadomości; karta kontaktowa v2. |
| Prokuratura Krajowa (`pk.gov.pl`) | READY_TO_CONTACT | [serwis](https://pk.gov.pl) | Brak źródłowo-specyficznego RSS/API i zasad; karta kontaktowa v2. Karty niezależnych sekcji `gov.pl` nie rozszerzają tej decyzji. |
| NIK (`nik.gov.pl`) | READY_TO_CONTACT | [ponowne wykorzystanie](https://www.nik.gov.pl/kontakt/ponowne-wykorzystywanie-informacji/) | Brak aktualnego, zweryfikowanego kanału dla tego rekordu; karta kontaktowa v2. Osobny feed NIK pozostaje osobnym źródłem. |
| KNF (`knf.gov.pl`) | READY_TO_CONTACT | [BIP / ponowne wykorzystanie](https://bip.knf.gov.pl/bip_portal/uknf/ponowne_wykorzystanie_informacji_sektora_publicznego) | Znaleziono rejestr RSS, ale nie ścisły kanał aktualności/eksport; karta kontaktowa v2. |
| Sąd Najwyższy (`sn.pl`) | READY_TO_CONTACT | [serwis](https://www.sn.pl) | Historyczny RSS zwracał 404; potrzeba aktualnego kanału; karta kontaktowa v3. |
| Parlament Europejski — Polska | READY_TO_CONTACT | [RSS](https://www.europarl.europa.eu/at-your-service/pl/stay-informed/rss-feeds), [legal notice](https://www.europarl.europa.eu/legal-notice/en) | Katalog RSS istnieje, ale dokładny polski XML nie został niezależnie potwierdzony; karta kontaktowa v3. |

## Wynik

- 2 źródła są `READY_TO_RUN` w wąskim zakresie metadanych (dane.gov.pl, BDL GUS).
- 7 źródeł ma status `contact_required` i gotową do kontroli kartę kontaktową.
- Żadne z tych dziewięciu źródeł nie jest `EXCLUDED`.
- Nie wysłano maila, nie wykonano szerokiego harvestu i nie pobrano treści ani plików.

ELI jest już odrębnie skonfigurowanym źródłem aktywnym i nie wchodził do dziewięciu kart roboczych.

## Walidacja

`pytest backend/scraper/test_structured_metadata.py backend/scraper/test_resolve_remaining_draft_cards.py -q` → `6 passed`.
