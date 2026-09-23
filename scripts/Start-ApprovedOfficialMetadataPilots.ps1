<#
Approve the next three narrow, documented public-data pilots.

ELI: incremental metadata for official acts only; no PDFs or full texts.
dane.gov.pl and GUS BDL: one metadata-contract request each, not a dataset import.
KRS is intentionally not included: the project audit requires a formal access
decision before automated KRS access can be enabled.
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

# ELI is queued through the existing bounded worker task. It collects only
# changed DU/MP metadata covered by its approved card.
docker compose exec worker celery -A config call scraper.tasks.import_official_task --args='["eli"]'
