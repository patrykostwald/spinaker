param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"
docker compose exec backend python manage.py migrate news
docker compose exec backend python manage.py seed_official_thumbnail_policies --apply --reviewed-by $ReviewedBy
