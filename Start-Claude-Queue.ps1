param([ValidateRange(1,12)][int]$MaxHours = 10)
$ErrorActionPreference = 'Stop'
$runtime = "$PSScriptRoot\.runtime"
New-Item -ItemType Directory -Force $runtime | Out-Null
$pidPath = Join-Path $runtime 'claude-queue.pid'
if (Test-Path $pidPath) {
    $oldPid = [int](Get-Content $pidPath)
    if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) { throw "Claude queue already runs with PID $oldPid" }
    Remove-Item -LiteralPath $pidPath
}
$process = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList @(
    '-NoProfile','-ExecutionPolicy','Bypass','-File',"$PSScriptRoot\Run-Claude-Queue.ps1",'-MaxHours',"$MaxHours"
)
$process.Id | Set-Content $pidPath
Write-Output "Started Claude queue for at most $MaxHours hours, PID $($process.Id)."

