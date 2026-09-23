<#
Read-only, resumable audit of a small batch of inactive source candidates.

It makes bounded availability checks for official/publisher URLs and disclosed
RSS/sitemaps. It neither enables sources nor imports articles. The generated
report is a review queue; an editor still needs to record a matching access
card before any source can be activated.
#>

param(
    [ValidateRange(1, 48)] [int]$BatchSize = 24,
    [ValidateRange(1, 6)] [int]$Workers = 3
)

$ErrorActionPreference = "Stop"

docker compose exec backend python manage.py audit_next_source_candidates `
  --limit $BatchSize `
  --workers $Workers `
  --max-age-hours 168 `
  --output-prefix reports/source-candidate-audit-current

docker compose exec backend python manage.py harvester_preflight
