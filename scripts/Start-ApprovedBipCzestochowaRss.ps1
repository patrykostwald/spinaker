<# Approves only the exact RSS channel found in the official BIP navigation. #>

$ErrorActionPreference = 'Stop'
$sourceId = 571
$termsUrl = 'https://bip.czestochowa.pl/artykul/71521/1151613/ponowne-wykorzystywanie'

docker compose exec backend python manage.py prepare_confirmed_rss_candidate --source-id $sourceId --apply
docker compose exec backend python manage.py audit_sources --source-id $sourceId --force --workers 1 `
  --output-prefix reports/bip-czestochowa-rss-audit-current
docker compose exec backend python manage.py configure_audited_rss_metadata_source --source-id $sourceId `
  --terms-url $termsUrl `
  --evidence-note 'Official BIP reuse conditions and a directly linked, freshly audited RSS channel; metadata only.' `
  --reviewed-by 'redakcja spin.clinic' --daily-cap 24 --valid-days 180 --apply
docker compose exec backend python manage.py fetch_approved_rss_source --source-id $sourceId
docker compose exec backend python manage.py harvester_preflight --approved-only
