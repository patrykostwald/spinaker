<#
Start reviewed metadata-only RSS pilots for KNF and IPN.
Each source needs a fresh completed audit; the Django command refuses otherwise.
#>
param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

$pilots = @(
  @{
    Id = 19
    Terms = "https://intranet.knf.gov.pl/bip_portal/uknf/ponowne_wykorzystanie_informacji_sektora_publicznego"
    Note = "KNF allows free reuse of information from its BIP and website when the source website is identified."
  },
  @{
    Id = 24
    Terms = "https://ipn.gov.pl/pl/rss"
    Note = "IPN publishes RSS for distribution of article titles, short descriptions and links; this pilot stores metadata only."
  }
)

foreach ($pilot in $pilots) {
  docker compose exec backend python manage.py configure_audited_rss_metadata_source `
    --source-id $pilot.Id `
    --terms-url $pilot.Terms `
    --evidence-note $pilot.Note `
    --reviewed-by $ReviewedBy `
    --daily-cap 24 `
    --apply
  docker compose exec backend python manage.py shell -c "from scraper.rss_scraper import scrape_rss_source; print({'source_id': $($pilot.Id), 'new_boxes': scrape_rss_source($($pilot.Id))})"
}
