<#
Audits every currently stale, inactive source candidate in bounded batches.

This script is read-only with respect to the catalogue: it does not enable a
source, create an access instruction or import an article.  Each batch writes
its timestamped report through audit_next_source_candidates.  The command
skips candidates audited during the last seven days, so successive batches move
through the queue instead of repeatedly checking the first records.
#>

param(
  [ValidateRange(1, 48)] [int]$BatchSize = 48,
  [ValidateRange(1, 6)] [int]$Workers = 6,
  # 0 means: continue until no stale candidates remain.  Use a positive value
  # only when deliberately running a limited diagnostic pass.
  [ValidateRange(0, 1000)] [int]$MaxBatches = 0
)

# A candidate may legitimately fail its own TLS or availability probe.  Docker
# forwards that diagnostic on stderr; keep processing so Django can write the
# completed audit record and the next batch can continue.  Command exit codes
# are checked explicitly below.
$ErrorActionPreference = "Continue"
$completed = 0

$batch = 0
while ($true) {
  $batch++
  if ($MaxBatches -gt 0 -and $batch -gt $MaxBatches) { break }
  Write-Output "AUDIT_BATCH=$batch START"
  $output = @()
  & docker compose exec backend python manage.py audit_next_source_candidates `
    --limit $BatchSize `
    --workers $Workers `
    --max-age-hours 168 `
    --output-prefix reports/source-candidate-audit-current 2>&1 | Tee-Object -Variable output
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    Write-Output "AUDIT_BATCH=$batch COMMAND_ERROR=$exitCode"
    continue
  }
  if (($output -join "`n") -match "Brak kandydat") {
    Write-Output "AUDIT_QUEUE_COMPLETE"
    break
  }
  $completed++
  Write-Output "AUDIT_BATCH=$batch COMPLETE"
}

Write-Output "AUDYT_PACZEK=$completed"
docker compose exec backend python manage.py harvester_preflight --approved-only
if ($LASTEXITCODE -ne 0) { Write-Error "Approved-source preflight failed." }
docker compose exec backend python manage.py source_review_queue
if ($LASTEXITCODE -ne 0) { Write-Error "Source review queue report failed." }
docker compose exec backend python manage.py source_verification_register
if ($LASTEXITCODE -ne 0) { Write-Error "Source verification register failed." }
