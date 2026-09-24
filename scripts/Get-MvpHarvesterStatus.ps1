<# Show the local, read-only state of approved MVP harvesters. #>
$ErrorActionPreference = 'Stop'
docker compose ps
docker compose exec backend python manage.py mvp_harvester_status
docker compose exec backend python manage.py harvester_preflight --approved-only
docker compose exec backend python manage.py data_quality_status
docker compose exec backend python manage.py public_figure_registry_status
