<# Start the approved GIW RSS metadata harvester. #>
param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

docker compose exec backend python manage.py configure_giw_rss_source --apply --reviewed-by $ReviewedBy
if ($LASTEXITCODE -ne 0) { throw "Nie udało się skonfigurować RSS GIW." }
$sourceId = docker compose exec -T backend python manage.py shell -c "from news.models import Source; print(Source.objects.get(url='https://www.wetgiw.gov.pl/').pk)"
if ($LASTEXITCODE -ne 0 -or $sourceId -notmatch '^\d+$') { throw "Nie udało się odczytać identyfikatora źródła GIW." }
docker compose exec backend python manage.py fetch_approved_rss_source --source-id $sourceId
docker compose exec backend python manage.py harvester_preflight --approved-only
