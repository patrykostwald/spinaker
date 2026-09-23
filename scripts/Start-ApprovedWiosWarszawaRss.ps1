<#
Start the reviewed WIOS Warszawa RSS metadata pilot.

Only feed metadata and direct original links are imported. No article HTML,
images, attachments, video or full-text copies are downloaded.
#>

param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

$sourceId = 419
$terms = "https://bip.warszawa.wios.gov.pl/bip/ponowne-wykorzystywanie/291%2CPonowne-wykorzystywanie-informacji-sektora-publicznego.html"

docker compose exec backend python manage.py configure_audited_rss_metadata_source `
  --source-id $sourceId `
  --terms-url $terms `
  --evidence-note "WIOS Warszawa publishes reuse conditions for BIP information and information made available otherwise; source, creation/acquisition time and processing attribution are retained. RSS metadata only." `
  --reviewed-by $ReviewedBy `
  --daily-cap 24 `
  --apply

docker compose exec backend python manage.py fetch_approved_rss_source --source-id $sourceId
docker compose exec backend python manage.py harvester_preflight --approved-only
