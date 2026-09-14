$root = "$PSScriptRoot\.local\ai-coordination\claude"
$pidPath = "$PSScriptRoot\.runtime\claude-queue.pid"
$pidValue = if (Test-Path $pidPath) { [int](Get-Content $pidPath) } else { 0 }
$active = if ($pidValue) { [bool](Get-Process -Id $pidValue -ErrorAction SilentlyContinue) } else { $false }
Write-Output "Claude queue active: $active; PID: $pidValue"
foreach ($name in @('inbox','running','done','failed')) {
    $path = Join-Path $root $name
    $count = if (Test-Path $path) { @(Get-ChildItem $path -Filter '*.md' -File).Count } else { 0 }
    Write-Output "$name`: $count"
}

