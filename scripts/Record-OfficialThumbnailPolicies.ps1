param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"
docker compose exec backend python manage.py migrate news
if ($LASTEXITCODE -ne 0) { throw "Migracja news nie powiodła się; polityki miniaturek nie zostały zapisane." }
docker compose exec backend python manage.py seed_official_thumbnail_policies --apply --reviewed-by $ReviewedBy
if ($LASTEXITCODE -ne 0) { throw "Zapis polityk miniaturek nie powiódł się." }
