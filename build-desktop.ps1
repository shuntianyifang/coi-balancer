param([string]$Python = 'python', [switch]$IncludeWikiIcons)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& $Python -m pip install -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw 'Failed to install desktop dependencies.' }
# Stage only distributable assets by default. Downloaded game art retains its own rights.
$stage = Join-Path $PSScriptRoot ('build\desktop-web-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Item -Path 'web\*.js','web\*.html','web\*.json' -Destination $stage -Force
New-Item -ItemType Directory -Force -Path "$stage\icons" | Out-Null
Copy-Item -Path 'web\icons\*.svg','web\icons\*.md','web\icons\wiki-manifest.json' -Destination "$stage\icons" -Force
if ($IncludeWikiIcons) {
    Copy-Item -Path 'web\icons\wiki_*.png' -Destination "$stage\icons" -Force
    Copy-Item -Path 'web\icons\wiki-notices' -Destination "$stage\icons" -Recurse -Force
}
& $Python -m PyInstaller --noconfirm --clean --windowed --onedir --name CoI-Balancer --add-data "$stage;web" --collect-all scipy desktop.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
Copy-Item LICENSE,THIRD_PARTY_NOTICES.md -Destination 'dist\CoI-Balancer' -Force
& $Python collect_desktop_licenses.py 'dist\CoI-Balancer\licenses'
if ($LASTEXITCODE -ne 0) { throw 'Failed to collect dependency notices.' }
@'
双击 CoI-Balancer.exe 打开，无需安装 Python 或手动启动服务器。
Windows 10/11，需要 Microsoft Edge WebView2 Runtime（大多数系统已安装）。
方案保存在 %LOCALAPPDATA%\CoI Balancer\scenarios.json，升级时会保留。
完整保留本文件夹内的 _internal 目录。关闭窗口即退出程序。
默认包使用项目 SVG；可将本地下载的 Wiki 图标放入 _internal\web\icons。
代码采用 MIT；第三方图标与依赖采用各自许可，详见 THIRD_PARTY_NOTICES.md。
'@ | Set-Content -Encoding utf8 'dist\CoI-Balancer\使用说明.txt'
Compress-Archive -Path 'dist\CoI-Balancer' -DestinationPath 'dist\CoI-Balancer-Windows.zip' -Force
Write-Host 'Portable package: dist\CoI-Balancer-Windows.zip'
