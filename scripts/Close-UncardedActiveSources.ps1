<#
Fails closed for configured sources that lack a current reviewed access card.
It never contacts publishers, sends mail, creates accounts, or downloads content.
#>

param([string]$ReviewedBy = "catalog safety gate")

$ErrorActionPreference = "Stop"

docker compose exec backend python manage.py demote_uncarded_active_sources --apply --reviewed-by $ReviewedBy
if ($LASTEXITCODE -ne 0) { throw "Uncarded active sources could not be demoted." }

docker compose exec backend python manage.py source_verification_register
if ($LASTEXITCODE -ne 0) { throw "Source verification register failed." }

docker compose exec backend python manage.py source_contact_register
if ($LASTEXITCODE -ne 0) { throw "Source contact preparation register failed." }

docker compose exec backend python manage.py source_catalog_completion_audit --strict
if ($LASTEXITCODE -ne 0) { throw "Source catalog completion audit failed." }
