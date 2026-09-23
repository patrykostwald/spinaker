param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

foreach ($sourceKey in @("cyfryzacja", "kultura", "rozwoj", "nauka", "gis", "gios", "rars", "kowr", "rodzina", "sport", "gdos", "kis", "ncbr", "paa", "wug", "gugik", "prokuratoria", "gddkia", "kgpsp", "gitd", "udsc", "uzp")) {
  docker compose exec backend python manage.py configure_official_gov_metadata_source --source-key $sourceKey --apply --reviewed-by $ReviewedBy
  if ($LASTEXITCODE -ne 0) { throw "Nie udało się skonfigurować źródła $sourceKey." }
  docker compose exec backend python manage.py import_official_gov_metadata --source-key $sourceKey --apply --limit 10
  if ($LASTEXITCODE -ne 0) { throw "Nie udało się pobrać metadanych źródła $sourceKey." }
}

docker compose exec backend python manage.py seed_official_thumbnail_policies --apply --reviewed-by $ReviewedBy
docker compose exec backend python manage.py harvester_preflight --approved-only
