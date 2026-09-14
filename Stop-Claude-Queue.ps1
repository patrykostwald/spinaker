$queueRoot = "$PSScriptRoot\.local\ai-coordination"
New-Item -ItemType Directory -Force $queueRoot | Out-Null
New-Item -ItemType File -Force (Join-Path $queueRoot 'STOP_CLAUDE_QUEUE') | Out-Null
$pidPath = "$PSScriptRoot\.runtime\claude-queue.pid"
if (Test-Path $pidPath) {
    $pidValue = [int](Get-Content $pidPath)
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if ($process) { Stop-Process -Id $pidValue }
    Remove-Item -LiteralPath $pidPath
}
Write-Output 'Claude queue stopped.'

