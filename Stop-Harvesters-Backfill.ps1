$ErrorActionPreference = 'Stop'
$pidPath = "$PSScriptRoot\.runtime\harvesters-backfill.pid"
if (-not (Test-Path $pidPath)) { Write-Output 'No recorded archive backfill process.'; exit 0 }
$pid = [int](Get-Content $pidPath)
$process = Get-Process -Id $pid -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $pid
    Write-Output "Stop requested for archive backfill PID $pid"
} else {
    Write-Output "Recorded archive backfill PID $pid is not running."
}
Remove-Item $pidPath -Force