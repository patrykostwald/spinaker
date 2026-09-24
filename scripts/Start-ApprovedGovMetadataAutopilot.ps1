<#
Configures and starts every reviewed gov.pl metadata-only source.

The Python allowlist is the gate: this script cannot activate an arbitrary URL.
Each configured source receives short-lived HTML and robots cards, a 24-request
daily cap and a three-second host interval. It never imports images, PDFs,
video or full article text.
#>
param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

# Keep this list explicit and in the same vocabulary as
# scraper.gov_metadata_listing.OFFICIAL_GOV_LISTINGS. Adding a new source still
# requires a reviewed entry there with its official section and, where needed,
# source-specific reuse terms.
$sourceKeys = @(
  "cyfryzacja", "edukacja", "gddkia", "gdos", "gif", "gis", "gios", "gitd",
  "govtech", "gugik", "infrastruktura", "kas", "kgpsp", "kis", "klimat",
  "kontaktoze", "kowr", "kultura", "map", "mon", "msz", "nauka", "ncbr",
  "nfosigw", "paa", "priorytety", "prokuratoria", "rars", "rolnictwo",
  "rodzina", "rozwoj", "rpp", "sluzby_specjalne", "sprawiedliwosc", "sport",
  "udsc", "urpl", "uzp", "wug", "zdrowie"
)

foreach ($sourceKey in $sourceKeys) {
  docker compose exec backend python manage.py configure_official_gov_metadata_source `
    --source-key $sourceKey --apply --reviewed-by $ReviewedBy
  if ($LASTEXITCODE -ne 0) { throw "Nie udało się skonfigurować źródła $sourceKey." }

  docker compose exec backend python manage.py import_official_gov_metadata `
    --source-key $sourceKey --apply --limit 10
  if ($LASTEXITCODE -ne 0) { throw "Nie udało się pobrać metadanych źródła $sourceKey." }
}

docker compose exec backend python manage.py seed_official_thumbnail_policies `
  --apply --reviewed-by $ReviewedBy
docker compose exec backend python manage.py harvester_preflight --approved-only
