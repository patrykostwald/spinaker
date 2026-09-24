<#
Start the reviewed GIOS RSS metadata pilot.

The access card is limited to the RSS feed discovered in the fresh source audit.
It imports only title, direct URL, date and feed summary. It does not fetch article
HTML, images, attachments, video or full-text copies.
#>

param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

$sourceId = 404
$terms = "https://powietrze.gios.gov.pl/depoz/regulamin-i-polityka-prywatnosci/"

docker compose exec backend python manage.py configure_audited_rss_metadata_source `
  --source-id $sourceId `
  --terms-url $terms `
  --evidence-note "GIOS publishes reuse conditions requiring source, time of acquisition and processing attribution; RSS metadata only." `
  --reviewed-by $ReviewedBy `
  --daily-cap 24 `
  --apply

docker compose exec backend python manage.py fetch_approved_rss_source --source-id $sourceId
docker compose exec backend python manage.py harvester_preflight --approved-only
