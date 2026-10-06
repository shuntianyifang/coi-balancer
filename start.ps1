$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$runtime = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$parentRuntime = Join-Path (Split-Path $PSScriptRoot) '.venv\Scripts\python.exe'
if (!(Test-Path $runtime) -and (Test-Path $parentRuntime)) {
    $runtime = $parentRuntime
}
if (!(Test-Path $runtime)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create Python environment.' }
}
& $runtime -c "import scipy"
if ($LASTEXITCODE -ne 0) {
    & $runtime -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install dependencies.' }
}
& $runtime server.py
