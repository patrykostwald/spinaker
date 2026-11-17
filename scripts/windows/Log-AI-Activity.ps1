param(
    [ValidateSet('Codex','Claude','Mistral','Harvester')][string]$Actor,
    [Parameter(Mandatory=$true)][string]$Message
)
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path  # scripts/windows -> repository root
$folder = Join-Path $RepoRoot '.local\ai-coordination'
New-Item -ItemType Directory -Force $folder | Out-Null
$safe = ($Message -replace "[`r`n]+", ' ').Trim()
Add-Content -Encoding utf8 (Join-Path $folder 'activity.log') `
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $Actor | $safe"
