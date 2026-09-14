param([string]$DatabasePath = 'C:\Users\User\spin-clinic\backend\db.sqlite3')

$python = 'C:\Users\User\spin-clinic\.venv\Scripts\python.exe'
try {
    $probe = Join-Path $PSScriptRoot 'backend\scraper\live_status.py'
    $data = (& $python $probe $DatabasePath | ConvertFrom-Json)
    $rate = [math]::Round($data.archive_new_10m / 10, 1)
    $finished = $data.done + $data.errors + $data.quarantined
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
    Write-Output "URL RESULTS: success=$($data.done)   retry=$($data.errors)   quarantined=$($data.quarantined)   waiting=$($data.pending)   active=$($data.running)"
    Write-Output "ERROR ROUTING: retry/unclassified=$($data.errors_retry_or_unclassified)   adapter review=$($data.errors_adapter_review)   permission/contact=$($data.errors_permission_review)"
    Write-Output "QUARANTINE: terminal=$($data.quarantine_terminal)   attempts exhausted=$($data.quarantine_exhausted)"
    Write-Output "QUALITY: historical request success=$success%   |   queue sources=$($data.queued_sources)"
    Write-Output "LEGAL ACCESS: archive sources approved=$($data.legal_archive_sources)   |   instructions approved=$($data.access_instructions_approved) draft=$($data.access_instructions_draft)"
    Write-Output "SOURCE RECOVERY: open=$($data.recovery_open)   |   contact required=$($data.recovery_contact_required)"
    Write-Output '============================================================'
} catch {
    Write-Output 'ARCHIVE DATABASE: metrics temporarily unavailable.'
}
$configPath = Join-Path $PSScriptRoot '.runtime\harvesters-backfill.config.json'
if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    Write-Output "HARVESTERS: configured cap=$($config.workers), dynamic mode=$($config.dynamic_sources), one request/domain, interval >=3s"
}
$backfillPidPath = Join-Path $PSScriptRoot '.runtime\harvesters-backfill.pid'
if (Test-Path $backfillPidPath) {
    $backfillPid = [int](Get-Content $backfillPidPath)
    if (Get-Process -Id $backfillPid -ErrorAction SilentlyContinue) {
        Write-Output "HARVESTERS NOW: running (supervisor PID $backfillPid)"
    } else {
        Write-Output "HARVESTERS NOW: stopped; waiting for reviewed source access instructions"
    }
} else {
    Write-Output 'HARVESTERS NOW: stopped; waiting for reviewed source access instructions'
}
$continuationPidPath = Join-Path $PSScriptRoot '.runtime\harvesters-continuation.pid'
if (Test-Path $continuationPidPath) {
    $continuationPid = [int](Get-Content $continuationPidPath)
    $continuationActive = [bool](Get-Process -Id $continuationPid -ErrorAction SilentlyContinue)
    if ($continuationActive) {
        Write-Output "NEXT CYCLE: armed (watcher PID $continuationPid); dynamic approved-source pool, 32 workers, max 10h"
    } else {
        Write-Output "NEXT CYCLE: watcher PID $continuationPid is no longer active; inspect continuation log"
    }
}
