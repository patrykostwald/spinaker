<#
Approve the next three narrow, documented public-data pilots.

ELI: incremental metadata for official acts only; no PDFs or full texts.
dane.gov.pl and GUS BDL: one metadata-contract request each, not a dataset import.
KRS is intentionally not included: a future entity-only pilot needs a separate
review of the exact public endpoint and reuse terms. It must never discover or
match people, nor retain personal registry data.
#>

param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

docker compose exec backend python manage.py configure_eli_metadata_source `
    --apply --reviewed-by $ReviewedBy

docker compose exec backend python manage.py configure_structured_metadata_sources dane_gov `
    --apply --reviewed-by $ReviewedBy

docker compose exec backend python manage.py configure_structured_metadata_sources gus_bdl `
    --apply --reviewed-by $ReviewedBy

docker compose exec backend python manage.py preflight_structured_metadata_source dane_gov
docker compose exec backend python manage.py preflight_structured_metadata_source gus_bdl

# Run the existing bounded importer once. Calling the task directly avoids
# PowerShell/Celery JSON argument parsing and still enforces the approved ELI
# access card inside import_official_task.
docker compose exec backend python manage.py shell -c "from scraper.tasks import import_official_task; print(import_official_task.run('eli'))"
