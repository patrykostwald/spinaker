<#
Refreshes the reviewable MVP operating view from approved official sources.
It imports only official Sejm/Senat/European Parliament rosters, the KPRM cabinet
and the central MSWiA voivode roster, then creates
profiles from those exact records. It does not create X accounts, inspect KRS,
activate new sources, create access cards, download unapproved content or send mail.
#>

$ErrorActionPreference = 'Stop'

docker compose exec backend python manage.py mvp_harvester_status
docker compose exec backend python manage.py harvester_preflight --approved-only
docker compose exec backend python manage.py source_channel_confirmation_queue
docker compose exec backend python manage.py source_contact_register

docker compose exec backend python manage.py sync_parliamentary_roster --source sejm
docker compose exec backend python manage.py sync_parliamentary_roster --source senat
docker compose exec backend python manage.py sync_parliamentary_roster --source ep
docker compose exec backend python manage.py sync_parliamentary_public_figures --source sejm
docker compose exec backend python manage.py sync_parliamentary_public_figures --source senat
docker compose exec backend python manage.py sync_parliamentary_public_figures --source ep
docker compose exec backend python manage.py sync_public_figures --source cabinet
docker compose exec backend python manage.py sync_voivodes
docker compose exec backend python manage.py public_figure_registry_status
