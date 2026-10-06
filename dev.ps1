param([string]$Python)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!$Python) {
    $Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (!(Test-Path $Python)) { $Python = Join-Path (Split-Path $PSScriptRoot) '.venv\Scripts\python.exe' }
    if (!(Test-Path $Python)) { $Python = 'python' }
}
& $Python dev_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'Development launcher failed.' }
