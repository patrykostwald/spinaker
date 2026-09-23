<#
Starts the BIP Torun RSS metadata-only source after the fresh audit already
recorded by the complete candidate audit. It never retrieves article pages,
images, attachments, video or full text.
#>

param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"
$terms = "https://bip.torun.pl/artykul/7/1/name"

docker compose exec backend python manage.py configure_audited_rss_metadata_source `
  --source-host "bip.torun.pl" `
  --terms-url $terms `
  --evidence-note "BIP Torun reuse conditions expressly cover information published in this BIP and require source, time and processing attribution; RSS metadata only." `
  --reviewed-by $ReviewedBy `
  --daily-cap 24 `
  --apply
if ($LASTEXITCODE -ne 0) { throw "BIP Torun source card was not created." }

docker compose exec backend python manage.py fetch_approved_rss_source --source-host bip.torun.pl --apply
if ($LASTEXITCODE -ne 0) { throw "BIP Torun metadata import failed." }

docker compose exec backend python manage.py harvester_preflight --approved-only
