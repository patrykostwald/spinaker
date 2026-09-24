<#
Checks only explicitly linked RSS/Atom feeds for inactive institution candidates.
It never guesses URLs, enables a source, creates an access card, imports content
or sends mail. Re-run until the command reports pending=0.
#>
param(
  [ValidateRange(1, 24)] [int]$BatchSize = 12,
  [ValidateRange(1, 3)] [int]$Workers = 2,
  [ValidateRange(0, 100)] [int]$MaxBatches = 0
)

$ErrorActionPreference = 'Stop'
$batch = 0
while ($true) {
  $batch++
  if ($MaxBatches -gt 0 -and $batch -gt $MaxBatches) { break }
  $output = & docker compose exec backend python manage.py discover_institution_source_channels `
  --limit $BatchSize --workers $Workers --apply --finalize-contact 2>&1
  $output | Write-Output
  if (($output -join "`n") -match 'pending=0') { break }
}
