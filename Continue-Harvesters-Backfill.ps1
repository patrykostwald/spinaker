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
$transitionPath = "$PSScriptRoot\.runtime\harvesters-transition.lock"

function Write-ContinuationLog([string]$Message) {
    "$(Get-Date -Format o) $Message" | Add-Content -LiteralPath $logPath
}

Write-ContinuationLog "Watching PID $ExpectedPid for natural completion."
while ($true) {
    if (-not (Test-Path -LiteralPath $pidPath)) {
        Write-ContinuationLog 'Cancelled because the active PID file was removed.'
        exit 0
    }
    try {
        $recordedPid = [int](Get-Content -LiteralPath $pidPath -ErrorAction Stop)
    } catch {
        Write-ContinuationLog 'Cancelled because the active PID file disappeared while being checked.'
        exit 0
    }
    if ($recordedPid -ne $ExpectedPid) {
        Write-ContinuationLog "Cancelled because active PID changed to $recordedPid."
        exit 0
    }
    if (-not (Get-Process -Id $ExpectedPid -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Seconds $PollSeconds
}

$transition = $null
try {
    try {
        $transition = [System.IO.File]::Open($transitionPath,
            [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None)
    } catch [System.IO.IOException] {
        Write-ContinuationLog 'Cancelled because another transition already owns the start lock.'
        exit 0
    }
    $transition.Close()
    $transition = $null

    # Re-check under the transition lock. A manual start is rejected by the
    # same lock, while a manual stop removes the PID file and cancels here.
    if (-not (Test-Path -LiteralPath $pidPath)) {
        Write-ContinuationLog 'Cancelled because the PID file was removed before transition ownership.'
        exit 0
    }
    $recordedPid = [int](Get-Content -LiteralPath $pidPath -ErrorAction Stop)
    if ($recordedPid -ne $ExpectedPid) {
        Write-ContinuationLog "Cancelled because active PID changed to $recordedPid before transition."
        exit 0
    }
    Remove-Item -LiteralPath $pidPath -Force
    Write-ContinuationLog 'Starting the next bounded cycle with the dynamic approved-source pool.'
    & "$PSScriptRoot\Start-Harvesters-Backfill.ps1" -DynamicSources -ContinuationOwned `
        -Workers $Workers -LimitPerSource $LimitPerSource -MaxHours $NextMaxHours `
        -DatabasePath $DatabasePath | Add-Content -LiteralPath $logPath
} catch {
    Write-ContinuationLog "Continuation failed: $($_.Exception.Message)"
    throw
} finally {
    if ($transition) { $transition.Close() }
    Remove-Item -LiteralPath $transitionPath -Force -ErrorAction SilentlyContinue
}
