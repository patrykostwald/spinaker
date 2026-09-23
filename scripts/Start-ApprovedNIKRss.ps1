<#
Start one legal, bounded NIK RSS source.

It records a versioned access card and makes one initial RSS read. The worker
then refreshes the same feed hourly through the normal access gate. It stores
only feed metadata and direct links; it never traverses NIK article pages.
#>

param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

docker compose exec backend python manage.py configure_nik_rss_source --apply --reviewed-by $ReviewedBy
docker compose exec backend python manage.py shell -c "from news.models import Source; from scraper.rss_scraper import scrape_rss_source; print({'new_boxes': scrape_rss_source(Source.objects.get(url='https://www.nik.gov.pl/rss/').pk)})"
