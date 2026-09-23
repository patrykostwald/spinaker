<#
Configures the reviewed SUDOP metadata card. Passing -RunOneCycle additionally
performs exactly one API request with the explicit, process-local pilot flag.
#>
param(
  [string]$ReviewedBy = "redakcja spin.clinic",
  [switch]$RunOneCycle,
  # Publiczny numer programu pomocy odczytany z oficjalnego słownika SUDOP.
  [string]$AidSourceNumber = "SA.124168"
)

$ErrorActionPreference = "Stop"

docker compose exec backend python manage.py configure_uokik_sudop_source --apply --reviewed-by $ReviewedBy

if ($RunOneCycle) {
  if ([string]::IsNullOrWhiteSpace($AidSourceNumber)) { throw "Podaj -AidSourceNumber z oficjalnego słownika SUDOP." }
  docker compose exec -e UOKIK_SUDOP_PILOT_ENABLED=true -e UOKIK_SUDOP_AID_SOURCE_NUMBER=$AidSourceNumber backend python manage.py run_uokik_sudop_pilot --apply
}

docker compose exec backend python manage.py harvester_preflight --approved-only
