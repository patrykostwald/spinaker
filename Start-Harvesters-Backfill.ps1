param(
    [Parameter(Mandatory=$true)][int[]]$SourceId,
    [ValidateSet('2026-09-14T23:59:59+02:00')][string]$CutoffAt = '2026-09-14T23:59:59+02:00',
    [ValidateRange(1,32)][int]$Workers = 2,
    [ValidateRange(1,100)][int]$LimitPerSource = 20,
    [string]$DatabasePath = "$PSScriptRoot\backend\db.sqlite3"
)

$ErrorActionPreference = 'Stop'
$python = @(
    "$PSScriptRoot\.venv\Scripts\python.exe",
    "$PSScriptRoot\backend\.venv\Scripts\python.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
$pidPath = "$PSScriptRoot\.runtime\harvesters-backfill.pid"
$logPath = "$PSScriptRoot\.runtime\harvesters-backfill.log"
$errorPath = "$PSScriptRoot\.runtime\harvesters-backfill.err.log"
if (-not $python) { throw "Missing Python virtualenv in project root or backend directory." }
if (Test-Path $pidPath) {
    $oldPid = [int](Get-Content $pidPath)
    if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) { throw "Backfill already running with PID $oldPid" }
    Remove-Item $pidPath -Force
}
New-Item -ItemType Directory -Force (Split-Path $pidPath) | Out-Null
$env:USE_SQLITE = 'true'
$env:ARCHIVE_STORE_FULL_TEXT = 'false'
$env:SQLITE_DATABASE_PATH = $DatabasePath
$ids = ($SourceId | ForEach-Object { "--source-id $_" }) -join ' '
$arguments = "manage.py backfill_archives $ids --cutoff-at `"$CutoffAt`" --workers $Workers --limit-per-source $LimitPerSource"
$process = Start-Process -FilePath $python -WorkingDirectory "$PSScriptRoot\backend" -ArgumentList $arguments -RedirectStandardOutput $logPath -RedirectStandardError $errorPath -PassThru
$process.Id | Set-Content $pidPath
Write-Output "Started archive backfill PID $($process.Id), cutoff $CutoffAt, workers $Workers, database $DatabasePath"
