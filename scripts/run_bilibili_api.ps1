$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "source\.venv\Scripts\python.exe"
$previousUtf8 = $env:PYTHONUTF8
$env:PYTHONUTF8 = "1"
try {
    & $python -m uvicorn adapter.bilibili_app:app --host 127.0.0.1 --port 8102
    exit $LASTEXITCODE
}
finally {
    if ($null -eq $previousUtf8) { Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue }
    else { $env:PYTHONUTF8 = $previousUtf8 }
}

