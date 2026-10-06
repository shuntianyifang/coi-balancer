param([Parameter(Mandatory=$true)][string]$GameDirectory)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$managed = Join-Path $GameDirectory 'Captain of Industry_Data\Managed'
if (!(Test-Path "$managed\Mafi.Unity.dll")) { throw 'Missing game UI assembly.' }
$sdk = (& dotnet --list-sdks | Select-Object -Last 1)
$version = $sdk.Split(' ')[0]
$sdkRoot = $sdk.Substring($sdk.IndexOf('[')+1).TrimEnd(']')
$compiler = Join-Path $sdkRoot "$version\Roslyn\bincore\csc.dll"
$output = Join-Path $PSScriptRoot 'build\mod\BalancerPlanner'
New-Item -ItemType Directory -Force $output | Out-Null
$references = @('mscorlib','System','System.Core','System.Xml','netstandard','System.Runtime.Serialization','Mafi','Mafi.Core','Mafi.Unity','UnityEngine.CoreModule','UnityEngine.IMGUIModule','UnityEngine.InputLegacyModule','UnityEngine.TextRenderingModule') | ForEach-Object { '/reference:' + (Join-Path $managed "$_.dll") }
& dotnet $compiler /nologo /target:library /nostdlib+ /langversion:latest "/out:$output\BalancerPlanner.dll" $references mod\*.cs
if ($LASTEXITCODE -ne 0) { throw 'In-game mod compilation failed.' }
Copy-Item mod\manifest.json,LICENSE -Destination $output -Force
Write-Host "Mod folder: $output"
