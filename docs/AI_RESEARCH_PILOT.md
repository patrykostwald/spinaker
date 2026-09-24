# Dr Spin: web research pilot

Implemented in `backend/news/ai_research.py` and `packages/ui/src/components/AIResearch.tsx`.

- GET `/api/ai/research/`: enabled status; no credential values.
- POST: `query`, `mode=context|verify`. Verify is staff-only (anonymous and nonstaff receive 403 before any attempt reservation). It additionally requires `speaker` and `statement` (pasted quote, not authenticated by the system). Verify query must be a public statement URL; X status URLs remain references only and are not imported or scraped. Other URLs must match an active archive source.
- No automatic publication. Returns `requires_review=true`, annotated AI text, and discovered source links. Dates remain null until publisher import. Cited URLs already present in Article are returned in archive_timeline (up to 15), ordered by existing publication dates; undated records follow separately. Frontend renders TimelineGrid and collapses the context analysis note. New links stay visibly pending metadata verification. This is not yet structured model event selection or streaming.
- Source citations must intersect provider-reported consulted web-search URLs and the current active source allowlist. This verifies citation provenance, **not entailment of every sentence or access to complete articles**. There is no guarantee of model impartiality.
- Only discovered URLs enter ArchiveJob. Generated titles, dates, classifications, quotations and analysis never enter Article records. Existing publisher importer remains responsible for metadata validation.
- A consulted source list does not prove fulltext access. Both prompt and UI state this limitation.

## Configuration, deliberately disabled by default

Set server environment only:

```
DR_SPIN_RESEARCH_ENABLED=true
OPENAI_API_KEY=<server secret>
DR_SPIN_RESEARCH_MODEL=<model supporting Responses web_search>
DR_SPIN_RESEARCH_DAILY_LIMIT=20
```

No real paid request was made while implementing. API model availability and real response behavior need a configured-key pilot. No default paid model is silently selected. Domain set is taken from active, scrape-enabled Source rows excluding X/editorial identities, exact-host result validation. More than 100 domains fails visibly rather than silently excluding sources. Future expansion needs batching and a measured budget.

Durable global attempt cap: 20/day default, includes failed provider calls, survives cache clear and restart. Per-client throttle: anonymous 6/hour, signed-in 10/hour (Django cache; global cap remains durable). Each provider call has max_output_tokens=4000, max_tool_calls=4; no retries; redirect following disabled; response 512 KiB cap and bounded timeout. The attempt cap is not a precise monetary budget; provider project spend limits and usage monitoring remain needed before public exposure. Store=false disables provider response storage for this API request; it is not a blanket assertion about all provider retention policies.

## Verification

10 mocked tests cover disabled no-call path, cited URL intersection/host spoofing/range rejection, URL-only archive persistence, durable daily limit, verify quote/identity requirements, X reference-only handling, outgoing cost bounds/no redirects, incomplete response failure, uncharged GET status polling, and chronology from existing publisher metadata rather than model dates. Provider integration remains untested against a live key.

Official documentation checked: https://developers.openai.com/api/docs/guides/tools-web-search (Responses web_search filters up to 100 domains, provider citations and consulted sources). This local pilot validates exact configured hosts more strictly than the provider's subdomain-inclusive filter.


## Durable operational audit

Migration 0016 adds AIResearchCall, recorded before each provider attempt and finalized with observed provider metrics. Missing input/output tokens or missing response output stay null. A confirmed empty output list yields zero web-search items; network failures do not. The audit omits prompts, statements, output prose, URLs and API credentials. It is a usage observation record, not a billing estimate. `python manage.py ai_preflight` reports read-only configuration presence and known/unknown usage, without contacting the provider. Owner instructions: `docs/AI_START_CHECKLIST_PL.md`.


### Tożsamość źródeł na wspólnej domenie

Lista domen dla wyszukiwarki jest unikalna, lecz rejestr zachowuje wszystkie
skonfigurowane, aktywne źródła. Dla `gov.pl` każdy wynik musi pasować do
`/web/{instytucja}` wskazanego w adresie źródła. Nieznany lub niejednoznaczny
zakres nie jest etykietowany ani kierowany do importu. Inne współdzielone
hosty wymagają jednoznacznego dopasowania skonfigurowanej ścieżki.
Wyniki już zapisane w archiwum także muszą mieć zgodną tożsamość źródła;
podobieństwo domeny nie wystarcza do przypisania dokumentu instytucji.
