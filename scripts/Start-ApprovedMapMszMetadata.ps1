param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"
foreach ($sourceKey in @("map", "msz")) {
  docker compose exec backend python manage.py configure_official_gov_metadata_source --source-key $sourceKey --apply --reviewed-by $ReviewedBy
  docker compose exec backend python manage.py import_official_gov_metadata --source-key $sourceKey --apply --limit 10
}
docker compose exec backend python manage.py harvester_preflight --approved-only
