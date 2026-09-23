<#
Starts the ABW RSS metadata-only source after refreshing its technical audit.
The official ABW RSS page describes distribution of news and communiques through
RSS with a title, short description and original link. This script never fetches
article pages, images, attachments, video or full text.
#>

param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"
$terms = "https://www.abw.gov.pl/pl/rss"

docker compose exec backend python manage.py configure_audited_rss_metadata_source `
  --source-host "abw.gov.pl" `
  --terms-url $terms `
  --evidence-note "Official ABW RSS page describes distribution of news and communiques with title, short description and original link; metadata only." `
  --reviewed-by $ReviewedBy `
  --daily-cap 24 `
  --apply
if ($LASTEXITCODE -ne 0) { throw "ABW source card was not created." }

docker compose exec backend python manage.py fetch_approved_rss_source --source-host abw.gov.pl --apply
if ($LASTEXITCODE -ne 0) { throw "ABW metadata import failed." }

docker compose exec backend python manage.py harvester_preflight --approved-only
