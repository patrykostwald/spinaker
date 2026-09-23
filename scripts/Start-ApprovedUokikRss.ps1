param(
  [int]$SourceId = 17,
  [string]$ReviewedBy = "redakcja spin.clinic"
)

$ErrorActionPreference = "Stop"

# This first phase remains read-only as to harvested materials. If the official
# feed is blocked or malformed, the script stops before it creates an access card.
docker compose exec backend python manage.py prepare_uokik_rss_candidate --source-id $SourceId --apply
docker compose exec backend python manage.py audit_sources --source-id $SourceId --force --workers 1 --output-prefix reports/uokik-rss-audit-current
docker compose exec backend python manage.py configure_audited_rss_metadata_source --source-id $SourceId `
  --terms-url https://uokik.gov.pl/bip/wnioskowanie-o-dostep-do-informacji-sektora-publicznego-w-celu-jej-ponownego-wykorzystywania `
  --evidence-note "Oficjalny katalog RSS UOKiK i warunki ponownego wykorzystania sprawdzone; wyłącznie tytuł, URL, data i streszczenie kanału." `
  --reviewed-by $ReviewedBy --apply
docker compose exec backend python manage.py fetch_approved_rss_source --source-id $SourceId
docker compose exec backend python manage.py harvester_preflight --approved-only
