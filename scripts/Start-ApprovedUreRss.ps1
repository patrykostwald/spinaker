<# Start the approved URE RSS metadata harvester. #>
param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

docker compose exec backend python manage.py configure_ure_rss_source --apply --reviewed-by $ReviewedBy
if ($LASTEXITCODE -ne 0) { throw "Nie udało się skonfigurować RSS URE." }
$sourceId = docker compose exec -T backend python manage.py shell -c "from news.models import Source; print(Source.objects.get(url='https://www.ure.gov.pl/').pk)"
if ($LASTEXITCODE -ne 0 -or $sourceId -notmatch '^\d+$') { throw "Nie udało się odczytać identyfikatora źródła URE." }
docker compose exec backend python manage.py fetch_approved_rss_source --source-id $sourceId
docker compose exec backend python manage.py harvester_preflight --approved-only
