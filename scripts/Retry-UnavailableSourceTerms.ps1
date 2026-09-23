<#
Retries only sources whose previous public terms-page check was unavailable.
It waits seven days by default to avoid repeatedly hitting unavailable hosts.
It never enables a source, creates a card, imports content or sends mail.
#>

param(
  [ValidateRange(1, 48)] [int]$BatchSize = 24,
  [ValidateRange(1, 6)] [int]$Workers = 3,
  [ValidateRange(1, 90)] [int]$MinAgeDays = 7
)

$ErrorActionPreference = 'Stop'
$batch = 0
while ($true) {
  $batch++
  Write-Output "TERMS_RETRY_BATCH=$batch START"
  $output = & docker compose exec backend python manage.py discover_source_reuse_terms `
    --only-unavailable --max-age-days $MinAgeDays --limit $BatchSize --workers $Workers --apply
  $exitCode = $LASTEXITCODE
  $output | ForEach-Object { Write-Output $_ }
  if ($exitCode -ne 0) { throw "Terms retry batch $batch failed." }
  if (($output -join "`n") -match 'pending=0') { break }
}
docker compose exec backend python manage.py source_resolution_matrix
if ($LASTEXITCODE -ne 0) { throw 'Source resolution matrix refresh failed.' }
