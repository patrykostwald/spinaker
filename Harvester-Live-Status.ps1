param([string]$DatabasePath = 'C:\Users\User\spin-clinic\backend\db.sqlite3')

$python = 'C:\Users\User\spin-clinic\.venv\Scripts\python.exe'
try {
    $probe = Join-Path $PSScriptRoot 'backend\scraper\live_status.py'
    $data = (& $python $probe $DatabasePath | ConvertFrom-Json)
    $rate = [math]::Round($data.archive_new_10m / 10, 1)
    $finished = $data.done + $data.errors
    $success = if ($finished) { [math]::Round(100 * $data.done / $finished, 1) } else { 0 }
    Write-Output "Database: all_boxes=$($data.boxes), archive_boxes=$($data.archive_boxes)"
    Write-Output "Successful archive boxes: +10min=$($data.archive_new_10m), rate=$rate/min"
    Write-Output "URL candidates: pending=$($data.pending), leased=$($data.running)"
    Write-Output "Fetch results: done=$($data.done), errors=$($data.errors), queue_success=$success%"
    Write-Output "Sources: active=$($data.active_sources), queued=$($data.queued_sources)"
} catch {
    Write-Output 'Database metrics temporarily unavailable.'
}
$configPath = Join-Path $PSScriptRoot '.runtime\harvesters-backfill.config.json'
if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    Write-Output "Backfill: configured_workers=$($config.workers), selected_sources=$($config.source_count), host_interval=>=3s"
}
