param([int[]]$SourceId)
$ErrorActionPreference = 'Stop'
$python = @(
    "$PSScriptRoot\.venv\Scripts\python.exe",
    "$PSScriptRoot\backend\.venv\Scripts\python.exe",
    "$PSScriptRoot\..\..\.venv\Scripts\python.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $python) { throw "Missing Python virtualenv in project root or backend directory." }
$env:USE_SQLITE = 'true'
$env:ARCHIVE_STORE_FULL_TEXT = 'false'
$ids = if ($SourceId) { $SourceId | ForEach-Object { "--source-id $_" } } else { @() }
& $python "$PSScriptRoot\backend\manage.py" backfill_status @ids
if (Test-Path "$PSScriptRoot\.runtime\harvesters-backfill.log") {
    Get-Content "$PSScriptRoot\.runtime\harvesters-backfill.log" -Tail 20
}
