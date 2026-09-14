param([ValidateRange(2,300)][int]$RefreshSeconds = 60)

$ErrorActionPreference = 'SilentlyContinue'
$queue = Join-Path $PSScriptRoot '.local\ai-coordination\claude'
$worktree = Join-Path $PSScriptRoot '..\spinaker-claude-night'
$fileColumns = @(
    @{Name='Time'; Expression={$_.LastWriteTime.ToString('HH:mm:ss')}},
    @{Name='File'; Expression={$_.FullName.Substring($worktree.Length + 1)}}
)
$logColumns = @(
    @{Name='Time'; Expression={$_.LastWriteTime.ToString('HH:mm:ss')}},
    'Name',
    'Length'
)

while ($true) {
    Clear-Host
    Write-Output "spin.clinic - local AI work - $(Get-Date -Format 'HH:mm:ss')"
    Write-Output ''
    & (Join-Path $PSScriptRoot 'Status-Claude-Queue.ps1')
    Write-Output ''
    & (Join-Path $PSScriptRoot 'Harvester-Live-Status.ps1')
    Write-Output ''
    Write-Output 'Important AI activity:'
    $activity = Join-Path $queue '..\activity.log'
    if (Test-Path $activity) { Get-Content $activity -Tail 8 }
    Write-Output ''
    Write-Output 'Recently changed Claude files:'
    Get-ChildItem $worktree -File -Recurse |
        Where-Object { $_.FullName -notmatch '\\.git|\\.pytest_cache|__pycache__' } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 8 -Property $fileColumns |
        Format-Table -AutoSize
    Write-Output 'Latest task logs:'
    Get-ChildItem (Join-Path $queue 'logs') -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 4 -Property $logColumns |
        Format-Table -AutoSize
    Write-Output "Refresh: $RefreshSeconds seconds. Ctrl+C stops only this view."
    Start-Sleep -Seconds $RefreshSeconds
}
