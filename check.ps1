param([string]$Python, [switch]$SkipDesktop)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!$Python) {
    $Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (!(Test-Path $Python)) { $Python = Join-Path (Split-Path $PSScriptRoot) '.venv\Scripts\python.exe' }
    if (!(Test-Path $Python)) { $Python = 'python' }
}
& $Python -m unittest
if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
Get-ChildItem web\*.js | ForEach-Object {
    & node --check $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "JavaScript syntax failed: $($_.Name)" }
}
& node test_buildings.js
if ($LASTEXITCODE -ne 0) { throw 'Building math tests failed.' }
& node test_building_views.js
if ($LASTEXITCODE -ne 0) { throw 'Building view tests failed.' }
if (!$SkipDesktop) {
    New-Item -ItemType Directory -Force build | Out-Null
    $report = Join-Path $PSScriptRoot ('build\check-' + [guid]::NewGuid().ToString('N') + '.json')
    & $Python desktop.py --smoke-test $report
    if ($LASTEXITCODE -ne 0 -or !(Test-Path $report)) { throw 'Desktop startup failed.' }
    $result = Get-Content -Raw -Encoding UTF8 $report | ConvertFrom-Json
    if (!$result.ok -or !$result.serverStopped) { throw "Desktop check failed: $($result.message)" }
    Write-Host $result.message
}
Write-Host 'All checks passed.'
