$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (!(Test-Path $compiler)) { throw '.NET Framework compiler is required for the standalone mod tests.' }
$folder = Join-Path $PSScriptRoot 'build\mod-tests'
New-Item -ItemType Directory -Force $folder | Out-Null
& $compiler /nologo /target:exe /r:System.Runtime.Serialization.dll "/out:$folder\SnapshotTests.exe" mod\SnapshotModel.cs mod\tests\SnapshotTests.cs
if ($LASTEXITCODE -ne 0) { throw 'Mod test compilation failed.' }
& "$folder\SnapshotTests.exe" $folder
if ($LASTEXITCODE -ne 0) { throw 'Mod snapshot tests failed.' }
$manifest = Get-Content -Raw -Encoding UTF8 mod\manifest.json | ConvertFrom-Json
if (!$manifest.can_add_to_saved_game -or !$manifest.can_remove_from_saved_game) { throw 'Save add/remove declarations are missing.' }
$sources = Get-Content -Raw mod\*.cs
if ($sources -match '\.(AssignRecipe|AssignRecipes|SetPaused|SetBoosted|TryAddEntity|RemoveEntityNoChecks|ApplyConfig|RegisterData)\s*\(') { throw 'Simulation mutation found in mod sources.' }
if ($sources -match 'Mafi\.Serialization|ModConfig\s*=|JsonConfig\.') { throw 'Unexpected game-save persistence found.' }
if ($sources -match 'if\s*\(\s*!?\s*gameWasLoaded\s*\)\s*return') { throw 'Initialize must run for both new games and loaded saves.' }
if ($sources -match 'bool\s+isUiOnly') { throw 'The lifecycle boolean is gameWasLoaded, not isUiOnly.' }
Write-Host 'UI-only source and manifest checks passed. In-game add/save/remove/reload test is still required.'
