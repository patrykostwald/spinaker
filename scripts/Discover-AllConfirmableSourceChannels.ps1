<# Processes the small exact-channel queue in durable, short batches. #>

$ErrorActionPreference = 'Stop'
$batch = 0
while ($true) {
  $batch++
  Write-Output "CHANNEL_DISCOVERY_BATCH=$batch START"
  $output = & docker compose exec backend python manage.py discover_confirmable_source_channels --apply --limit 2 --workers 1
  $exitCode = $LASTEXITCODE
  $output | ForEach-Object { Write-Output $_ }
  if ($exitCode -ne 0) { throw "Channel discovery batch $batch failed." }
  if (($output -join "`n") -match 'pending=0') { break }
}
docker compose exec backend python manage.py source_channel_confirmation_queue
