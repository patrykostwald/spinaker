<# Start the reviewed Trybunal Konstytucyjny RSS metadata pilot. #>

param([string]$ReviewedBy = "redakcja spin.clinic")
$ErrorActionPreference = "Stop"

$terms = "https://trybunal.gov.pl/informacja-publiczna-media/ponowne-wykorzystywanie"
docker compose exec backend python manage.py configure_audited_rss_metadata_source `
  --source-id 10 `
  --terms-url $terms `
  --evidence-note "TK publishes source, creation/acquisition-time and processing attribution conditions." `
  --reviewed-by $ReviewedBy `
  --daily-cap 24 `
  --apply

docker compose exec backend python manage.py shell -c "from scraper.rss_scraper import scrape_rss_source; print({'new_boxes': scrape_rss_source(10)})"
