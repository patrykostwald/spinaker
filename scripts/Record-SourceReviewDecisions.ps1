<#
Records the completed technical audit as durable non-operational source decisions.
It never activates a source, creates an access card, sends mail, or imports data.
#>

$ErrorActionPreference = "Stop"

docker compose exec backend python manage.py materialize_source_review_decisions --apply
if ($LASTEXITCODE -ne 0) { throw "Source review decisions were not recorded." }

docker compose exec backend python manage.py source_verification_register
if ($LASTEXITCODE -ne 0) { throw "Source verification register failed." }

docker compose exec backend python manage.py source_contact_register
if ($LASTEXITCODE -ne 0) { throw "Source contact preparation register failed." }

docker compose exec backend python manage.py source_catalog_completion_audit
if ($LASTEXITCODE -ne 0) { throw "Source catalog completion audit failed." }
