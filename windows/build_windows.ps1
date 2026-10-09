$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "无法创建 Python 虚拟环境。请安装 64 位 Python 3.10+。" }
}

& $python -c "import struct; assert struct.calcsize('P') * 8 == 64, '需要 64 位 Python'"
if ($LASTEXITCODE -ne 0) { throw "需要 64 位 Python。" }
$pythonPlatform = (& $python -c "import sysconfig; print(sysconfig.get_platform().lower())").Trim()
if ($pythonPlatform -ne "win-amd64") { throw "此脚本面向 Windows x64；当前 Python 平台为 $pythonPlatform。" }

& $python -m pip install -r requirements.txt "pyinstaller>=6.18,<7"
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败。" }

& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "测试未通过，已停止打包。" }

& $python -m PyInstaller --noconfirm --clean --windowed --name "网易云音乐下载器" run.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败。" }

$appFolder = Join-Path $PSScriptRoot "dist\网易云音乐下载器"
if (-not (Test-Path (Join-Path $appFolder "网易云音乐下载器.exe"))) {
    throw "PyInstaller 没有生成应用程序。"
}

$isccCandidates = @(
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    (Join-Path ${env:ProgramFiles} "Inno Setup 7\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe")
)
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) {
    throw "未找到 Inno Setup 7 的 ISCC.exe。请先安装 Inno Setup 7，再重新运行脚本。"
}

& $iscc (Join-Path $PSScriptRoot "installer.iss")
if ($LASTEXITCODE -ne 0) { throw "安装程序打包失败。" }

$installer = Join-Path $PSScriptRoot "dist\installer\网易云音乐下载器-安装程序-Windows-x64.exe"
if (-not (Test-Path $installer)) { throw "安装程序未生成：$installer" }
Write-Host "可直接安装的单文件安装程序：$installer"
