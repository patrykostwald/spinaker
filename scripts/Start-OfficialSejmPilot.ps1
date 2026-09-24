<#
Start the first, deliberately narrow official-data import.

It approves only the documented Sejm voting API path and imports at most
12 requests from the first sitting.  It does not approve RSS, HTML, media,
or any other source.  Run from the repository root:
  .\scripts\Start-OfficialSejmPilot.ps1
#>

param(
    [string]$ReviewedBy = "redakcja spin.clinic",
    [int]$FromSitting = 1,
    [int]$ToSitting = 1,
    [int]$MaxRequests = 12
)

$ErrorActionPreference = "Stop"

docker compose exec backend python manage.py approve_official_api_sources `
    --apply `
    --reviewed-by $ReviewedBy `
    --evidence-url "https://www.sejm.gov.pl/sejm10.nsf/page.xsp/copyright"

docker compose exec backend python manage.py sejm_pilot_preflight

docker compose exec backend python manage.py backfill_sejm_votings `
    --from-sitting $FromSitting `
    --to-sitting $ToSitting `
    --max-requests $MaxRequests `
    --apply

docker compose exec backend python manage.py sejm_pilot_status
