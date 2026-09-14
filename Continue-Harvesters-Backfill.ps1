param(
    [Parameter(Mandatory=$true)][int]$ExpectedPid,
    [ValidateRange(1,360)][int]$PollSeconds = 60,
    [ValidateRange(0.1,24)][double]$NextMaxHours = 10,
    [ValidateRange(1,32)][int]$Workers = 32,
    [ValidateRange(1,100)][int]$LimitPerSource = 100,
    [string]$DatabasePath = 'C:\Users\User\spin-clinic\backend\db.sqlite3'
)

$ErrorActionPreference = 'Stop'
$pidPath = "$PSScriptRoot\.runtime\harvesters-backfill.pid"
$logPath = "$PSScriptRoot\.runtime\harvesters-continuation.log"

function Write-ContinuationLog([string]$Message) {
    "$(Get-Date -Format o) $Message" | Add-Content -LiteralPath $logPath
}

Write-ContinuationLog "Watching PID $ExpectedPid for natural completion."
while ($true) {
    if (-not (Test-Path -LiteralPath $pidPath)) {
        Write-ContinuationLog 'Cancelled because the active PID file was removed.'
        exit 0
    }
    $recordedPid = [int](Get-Content -LiteralPath $pidPath)
    if ($recordedPid -ne $ExpectedPid) {
        Write-ContinuationLog "Cancelled because active PID changed to $recordedPid."
        exit 0
    }
    if (-not (Get-Process -Id $ExpectedPid -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Seconds $PollSeconds
}

# The PID file still points at the naturally completed process, so this watcher
# owns the transition. A manual stop removes the file and exits above.
Remove-Item -LiteralPath $pidPath -Force
Write-ContinuationLog 'Starting the next bounded cycle with the dynamic approved-source pool.'
try {
    & "$PSScriptRoot\Start-Harvesters-Backfill.ps1" -DynamicSources -Workers $Workers `
        -LimitPerSource $LimitPerSource -MaxHours $NextMaxHours -DatabasePath $DatabasePath |
        Add-Content -LiteralPath $logPath
} catch {
    Write-ContinuationLog "Continuation failed: $($_.Exception.Message)"
    throw
}
