param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"
docker compose exec backend python manage.py configure_mswia_metadata_source --apply --reviewed-by $ReviewedBy
docker compose exec backend python manage.py import_mswia_metadata --apply --limit 10
docker compose exec backend python manage.py harvester_preflight --approved-only
