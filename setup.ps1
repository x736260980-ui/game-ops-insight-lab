$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location $root

if (-not (Test-Path -LiteralPath (Join-Path $root "source\main.py"))) {
    & (Join-Path $root "scripts\git.ps1") submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) {
        throw "MediaCrawler 子模块初始化失败。"
    }
}

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    throw "未找到 Python Launcher（py）。请先安装 Python 3.11 或更高版本。"
}

$venvPython = Join-Path $root "source\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    & py -3.11 -m venv (Join-Path $root "source\.venv")
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $root "source\requirements.txt")
& $venvPython -m pip install -r (Join-Path $root "requirements.txt")

$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) {
    throw "未找到 npm。请安装 Node.js 20.19+ 或 22.12+。"
}

Push-Location (Join-Path $root "insight-dashboard")
try {
    & npm ci
    & npm run build
}
finally {
    Pop-Location
}

Write-Host "安装完成。可启动 Dashboard 或三个采集服务。" -ForegroundColor Green
