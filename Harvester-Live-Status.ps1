param([string]$DatabasePath = 'C:\Users\User\spin-clinic\backend\db.sqlite3')

$python = 'C:\Users\User\spin-clinic\.venv\Scripts\python.exe'
try {
    $probe = Join-Path $PSScriptRoot 'backend\scraper\live_status.py'
    $data = (& $python $probe $DatabasePath | ConvertFrom-Json)
    $rate = [math]::Round($data.archive_new_10m / 10, 1)
    $finished = $data.done + $data.errors
    $success = if ($finished) { [math]::Round(100 * $data.done / $finished, 1) } else { 0 }
    $total = $finished + $data.pending + $data.running
    $progress = if ($total) { [math]::Round(100 * $finished / $total, 2) } else { 0 }
    $perHour = [math]::Round($rate * 60)
    $etaHours = if ($rate -gt 0) { [math]::Round($data.pending / ($rate * 60), 1) } else { $null }
    $eta = if ($null -eq $etaHours) { 'unknown' } elseif ($etaHours -gt 48) { "~$([math]::Round($etaHours / 24, 1)) days" } else { "~$etaHours hours" }
    Write-Output '============================================================'
    Write-Output '                  ARCHIVE DATABASE'
    Write-Output '============================================================'
    Write-Output "ARCHIVE BOXES SAVED: $($data.archive_boxes)   |   ALL BOXES: $($data.boxes)"
    Write-Output "NEW: +$($data.archive_new_10m) / 10 min   |   ~$rate/min   |   ~$perHour/hour"
    Write-Output "DISCOVERED QUEUE PROCESSED: $progress%   |   ETA at current rate: $eta"
    Write-Output "URL RESULTS: success=$($data.done)   error=$($data.errors)   waiting=$($data.pending)   active=$($data.running)"
    Write-Output "QUALITY: successful requests=$success%   |   sources active=$($data.active_sources) / queued=$($data.queued_sources)"
    Write-Output '============================================================'
} catch {
    Write-Output 'ARCHIVE DATABASE: metrics temporarily unavailable.'
}
$configPath = Join-Path $PSScriptRoot '.runtime\harvesters-backfill.config.json'
if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    Write-Output "HARVESTERS: configured=$($config.workers), approved sources=$($config.source_count), one request/domain, interval >=3s"
}
