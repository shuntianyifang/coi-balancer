$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$source = Join-Path $PSScriptRoot 'build\exporter\BalancerDataExporter'
if (!(Test-Path "$source\BalancerDataExporter.dll")) { throw 'Build the exporter first with build-exporter.ps1.' }
$target = Join-Path $env:APPDATA 'Captain of Industry\Mods\BalancerDataExporter'
if (Test-Path "$target\manifest.json") {
    $manifest = Get-Content -Encoding UTF8 -Raw "$target\manifest.json" | ConvertFrom-Json
    if ($manifest.id -ne 'BalancerDataExporter') { throw 'Target belongs to a different mod; refusing to overwrite.' }
}
New-Item -ItemType Directory -Force $target | Out-Null
try { Copy-Item -LiteralPath "$source\BalancerDataExporter.dll" -Destination $target -Force }
catch { throw 'Exporter DLL is in use or inaccessible. Close the game and retry. Existing exports are preserved.' }
Copy-Item -LiteralPath "$source\manifest.json" -Destination $target -Force
Copy-Item -LiteralPath 'LICENSE','exporter\README.md' -Destination $target -Force
Write-Host "Exporter updated: $target"
