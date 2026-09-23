<# Configure BZP and run exactly one metadata-only pilot cycle. #>
param([string]$ReviewedBy = 'redakcja spin.clinic')

$ErrorActionPreference = 'Stop'
docker compose exec backend python manage.py configure_bzp_metadata_source --apply --reviewed-by $ReviewedBy
docker compose exec -e BZP_API_ENABLED=true backend python manage.py shell -c "from scraper.bzp_backfill import bzp_backfill_cycle; print(bzp_backfill_cycle())"
