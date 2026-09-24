<# Classifies discovered terms pages only. It never enables sources or sends mail. #>
param([int]$BatchSize = 16, [int]$Workers = 3)
$ErrorActionPreference = "Stop"
$batch = 0
while ($true) {
  $batch++
  Write-Output "TERMS_CLASSIFICATION_BATCH=$batch START"
  $output = & docker compose exec backend python manage.py classify_source_reuse_terms --limit $BatchSize --workers $Workers --apply
  $exitCode = $LASTEXITCODE
  $output | ForEach-Object { Write-Output $_ }
  if ($exitCode -ne 0) { throw "Terms classification batch $batch failed." }
  if (($output -join "`n") -match "pending=0") { break }
}
