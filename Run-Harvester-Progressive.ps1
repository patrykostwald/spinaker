param(
    [Parameter(Mandatory=$true)][int[]]$SourceId,
    [ValidateSet('2026-09-14T23:59:59+02:00')][string]$CutoffAt = '2026-09-14T23:59:59+02:00',
    [string]$BaseDatabase = "$PSScriptRoot\backend\db.sqlite3",
    [string]$OutputDirectory = "$PSScriptRoot\reports\archive-pilot"
)

$ErrorActionPreference = 'Stop'
$python = @(
    "$PSScriptRoot\.venv\Scripts\python.exe",
    "$PSScriptRoot\backend\.venv\Scripts\python.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $python) { throw "Missing Python virtualenv in project root or backend directory." }
if (-not (Test-Path $BaseDatabase)) { throw "Missing base SQLite database: $BaseDatabase" }
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$ids = ($SourceId | ForEach-Object { "--source-id $_" }) -join ' '
$stages = @(2, 8, 16, 24, 32)
$results = @()
foreach ($workers in $stages) {
    $stageDir = Join-Path $OutputDirectory "workers-$workers"
    New-Item -ItemType Directory -Force $stageDir | Out-Null
    $database = Join-Path $stageDir 'db.sqlite3'
    Copy-Item $BaseDatabase $database -Force
    $stdout = Join-Path $stageDir 'stdout.log'
    $stderr = Join-Path $stageDir 'stderr.log'
    $env:USE_SQLITE = 'true'
    $env:ARCHIVE_STORE_FULL_TEXT = 'false'
    $env:SQLITE_DATABASE_PATH = $database
    $arguments = "manage.py backfill_archives $ids --cutoff-at `"$CutoffAt`" --workers $workers --limit-per-source 20"
    $started = Get-Date
    $process = Start-Process -FilePath $python -WorkingDirectory "$PSScriptRoot\backend" -ArgumentList $arguments -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -Wait
    $finished = Get-Date
    $results += [pscustomobject]@{
        workers = $workers
        exit_code = $process.ExitCode
        elapsed_seconds = [math]::Round(($finished - $started).TotalSeconds, 2)
        stdout = $stdout
        stderr = $stderr
        database = $database
        note = 'CPU/RAM/transfer and response percentiles require capture from the host monitor; do not infer them from elapsed time.'
    }
}
$results | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $OutputDirectory 'results.json')
$results | Format-Table -AutoSize
