param([int[]]$SourceId)
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path  # scripts/windows -> repository root
$ErrorActionPreference = 'Stop'
$python = @(
    "$RepoRoot\.venv\Scripts\python.exe",
    "$RepoRoot\backend\.venv\Scripts\python.exe",
    "$RepoRoot\..\..\.venv\Scripts\python.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $python) { throw "Missing Python virtualenv in project root or backend directory." }
$env:USE_SQLITE = 'true'
$env:SQLITE_DATABASE_PATH = 'C:\Users\User\spin-clinic\backend\db.sqlite3'
$env:ARCHIVE_STORE_FULL_TEXT = 'false'
$ids = if ($SourceId) { $SourceId | ForEach-Object { "--source-id $_" } } else { @() }
& $python "$RepoRoot\backend\manage.py" backfill_status @ids
if (Test-Path "$RepoRoot\.runtime\harvesters-backfill.log") {
    Get-Content "$RepoRoot\.runtime\harvesters-backfill.log" -Tail 20
}
