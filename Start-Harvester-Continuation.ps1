param(
    [ValidateRange(0.1,24)][double]$NextMaxHours = 10,
    [ValidateRange(1,32)][int]$Workers = 32,
    [ValidateRange(1,100)][int]$LimitPerSource = 100
)

$ErrorActionPreference = 'Stop'
$activePidPath = "$PSScriptRoot\.runtime\harvesters-backfill.pid"
$watcherPidPath = "$PSScriptRoot\.runtime\harvesters-continuation.pid"
if (-not (Test-Path -LiteralPath $activePidPath)) { throw 'No active backfill PID file.' }
$activePid = [int](Get-Content -LiteralPath $activePidPath)
if (-not (Get-Process -Id $activePid -ErrorAction SilentlyContinue)) { throw "Backfill PID $activePid is not running." }
if (Test-Path -LiteralPath $watcherPidPath) {
    $oldWatcher = [int](Get-Content -LiteralPath $watcherPidPath)
    if (Get-Process -Id $oldWatcher -ErrorAction SilentlyContinue) {
        throw "Continuation watcher already runs with PID $oldWatcher."
    }
    Remove-Item -LiteralPath $watcherPidPath -Force
}
$arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    "$PSScriptRoot\Continue-Harvesters-Backfill.ps1", '-ExpectedPid', $activePid,
    '-NextMaxHours', $NextMaxHours, '-Workers', $Workers, '-LimitPerSource', $LimitPerSource)
$watcher = Start-Process powershell.exe -WindowStyle Hidden -WorkingDirectory $PSScriptRoot `
    -ArgumentList $arguments -PassThru
$watcher.Id | Set-Content -LiteralPath $watcherPidPath
Write-Output "Continuation watcher PID $($watcher.Id) will follow backfill PID $activePid."
