<#
Run the local MVP readiness checks after pulling the branch or changing code.

The script does not deploy the service and does not seed production data. Django
pytest creates its own test database through the existing Compose backend.
#>

$ErrorActionPreference = "Stop"

docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend python -m pytest `
  scraper/test_apply_audited_feeds.py `
  scraper/test_audit_next_source_candidates.py `
  scraper/test_configure_nik_rss_source.py `
  scraper/test_configure_kprm_metadata_source.py `
  news/test_public_figures_api.py `
  news/test_personal_context.py -q

pnpm build:spin
