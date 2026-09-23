<#
Reviews every inactive candidate not already covered by an active source for
official reuse-condition links.
It only saves evidence for editorial review. It never enables sources,
downloads articles, creates access cards, or sends mail.
#>

param(
  [int]$BatchSize = 24,
  [int]$Workers = 3
)

$ErrorActionPreference = "Stop"
$batch = 0
while ($true) {
  $batch++
  Write-Output "TERMS_DISCOVERY_BATCH=$batch START"
  $output = & docker compose exec backend python manage.py discover_source_reuse_terms --limit $BatchSize --workers $Workers --apply
  $exitCode = $LASTEXITCODE
  $output | ForEach-Object { Write-Output $_ }
  if ($exitCode -ne 0) { throw "Terms discovery batch $batch failed." }
  if (($output -join "`n") -match "pending=0") { break }
}
docker compose exec backend python manage.py source_contact_register
if ($LASTEXITCODE -ne 0) { throw "Source contact register failed." }
