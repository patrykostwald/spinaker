$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path  # scripts/windows -> repository root
$ErrorActionPreference = 'Stop'
$pidPath = "$RepoRoot\.runtime\harvesters-backfill.pid"
if (-not (Test-Path $pidPath)) { Write-Output 'No recorded archive backfill process.'; exit 0 }
$backfillPid = [int](Get-Content $pidPath)
$process = Get-Process -Id $backfillPid -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $backfillPid
    Write-Output "Stop requested for archive backfill PID $backfillPid"
} else {
    Write-Output "Recorded archive backfill PID $pid is not running."
}
Remove-Item $pidPath -Force
