param(
    [datetime]$ResumeAt = (Get-Date '2026-09-14 08:21:00'),
    [string[]]$TaskNames = @('005-backfill-reliability-audit.md', '006-next-source-wave-audit.md')
)

$ErrorActionPreference = 'Stop'
$queue = Join-Path $PSScriptRoot '.local\ai-coordination\claude'
$failed = [IO.Path]::GetFullPath((Join-Path $queue 'failed'))
$inbox = [IO.Path]::GetFullPath((Join-Path $queue 'inbox'))
if (-not $failed.StartsWith([IO.Path]::GetFullPath($PSScriptRoot)) -or
    -not $inbox.StartsWith([IO.Path]::GetFullPath($PSScriptRoot))) {
    throw 'Queue path escaped the project worktree.'
}
while ((Get-Date) -lt $ResumeAt) {
    Start-Sleep -Seconds ([math]::Min(60, [math]::Max(1, ($ResumeAt - (Get-Date)).TotalSeconds)))
}
foreach ($name in $TaskNames) {
    $source = Join-Path $failed $name
    $target = Join-Path $inbox $name
    if ((Test-Path -LiteralPath $source) -and -not (Test-Path -LiteralPath $target)) {
        Move-Item -LiteralPath $source -Destination $target
    }
}
