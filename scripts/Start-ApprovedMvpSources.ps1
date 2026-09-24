<#
Start every source pilot that is already reviewed in this repository.

This is intentionally a short allowlist: Sejm is managed by its own pilot
script, while ELI/dane.gov/GUS, NIK and KPRM are started here. It never scans
or enables source candidates and never changes an access-card scope.
#>

param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

& "$PSScriptRoot\Start-ApprovedOfficialMetadataPilots.ps1" -ReviewedBy $ReviewedBy
& "$PSScriptRoot\Start-ApprovedNIKRss.ps1" -ReviewedBy $ReviewedBy
& "$PSScriptRoot\Start-ApprovedKprmMetadataPilot.ps1" -ReviewedBy $ReviewedBy

docker compose exec backend python manage.py harvester_preflight --approved-only
