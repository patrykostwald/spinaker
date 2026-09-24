$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

& (Join-Path $projectRoot 'Stop-Harvesters.ps1')
& (Join-Path $projectRoot 'Start-Harvesters.ps1') -Workers 32

Write-Host 'Tryb nocny działa z najwyższą potwierdzoną konfiguracją: 32 workery.'
