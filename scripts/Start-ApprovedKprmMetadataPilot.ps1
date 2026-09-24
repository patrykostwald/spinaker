<#
Start the reviewed, metadata-only KPRM listing pilot.

The card covers only the official premier section. It saves titles, dates,
source URLs and permitted metadata; it does not retain full article text, PDFs,
images, audio or video. The daily card cap is 24 requests.
#>

param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

docker compose exec backend python manage.py configure_kprm_metadata_source --apply --reviewed-by $ReviewedBy
docker compose exec backend python manage.py shell -c "from scraper.html_archive import kprm_listing_cycle; print(kprm_listing_cycle())"
