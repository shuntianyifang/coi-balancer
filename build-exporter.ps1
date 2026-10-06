param([Parameter(Mandatory=$true)][string]$GameDirectory)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$managed = Join-Path $GameDirectory 'Captain of Industry_Data\Managed'
if (!(Test-Path "$managed\Mafi.Core.dll")) { throw 'Missing Mafi.Core.dll' }
$sdk = (& dotnet --list-sdks | Select-Object -Last 1)
if (!$sdk) { throw '.NET SDK is required.' }
$version = $sdk.Split(' ')[0]
$sdkRoot = $sdk.Substring($sdk.IndexOf('[')+1).TrimEnd(']')
$compiler = Join-Path $sdkRoot "$version\Roslyn\bincore\csc.dll"
$output = Join-Path $PSScriptRoot 'build\exporter\BalancerDataExporter'
New-Item -ItemType Directory -Force $output | Out-Null
$references = @('mscorlib','System','System.Core','netstandard','Mafi','Mafi.Core') | ForEach-Object { '/reference:' + (Join-Path $managed "$_.dll") }
& dotnet $compiler /nologo /target:library /nostdlib+ /langversion:latest "/out:$output\BalancerDataExporter.dll" $references exporter\BalancerDataExporter.cs
if ($LASTEXITCODE -ne 0) { throw 'Exporter compilation failed.' }
Copy-Item exporter\manifest.json,LICENSE -Destination $output -Force
Write-Host "Mod folder ready: $output"

