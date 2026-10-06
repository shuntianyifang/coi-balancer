$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$source = Join-Path $PSScriptRoot 'build\mod\BalancerPlanner'
if (!(Test-Path "$source\BalancerPlanner.dll")) { throw 'Run build-mod.ps1 first.' }
$target = Join-Path $env:APPDATA 'Captain of Industry\Mods\BalancerPlanner'
if (Test-Path "$target\manifest.json") {
    $manifest = Get-Content -Encoding UTF8 -Raw "$target\manifest.json" | ConvertFrom-Json
    if ($manifest.id -ne 'BalancerPlanner') { throw 'Target directory belongs to another mod.' }
}
New-Item -ItemType Directory -Force $target | Out-Null
Copy-Item -LiteralPath "$source\BalancerPlanner.dll","$source\manifest.json",'LICENSE','mod\README.md' -Destination $target -Force
Write-Host "Installed: $target. Enable the mod in a test save and open the calculator with F8."
