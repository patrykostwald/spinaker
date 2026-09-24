<#
Refreshes the two read-only reports that close the source-audit decision loop.
It does not send messages, create contact cards, approve a source, or download
content. Run after activating a source so all totals reflect the current DB.
#>

$ErrorActionPreference = "Stop"

docker compose exec backend python manage.py source_verification_register
if ($LASTEXITCODE -ne 0) { throw "Source verification register failed." }

docker compose exec backend python manage.py source_contact_register
if ($LASTEXITCODE -ne 0) { throw "Source contact preparation register failed." }
