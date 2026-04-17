# Chi dong goi UNG DUNG SERVER trung tam: nhan du lieu tu agent/bot giam sat.
# Output: deploy\dist-control\monitoring-control-server.exe (+ auth.token)
# Chay:  Set-Location c:\BOT\monitoring\deploy ; .\build_control_server.ps1

$ErrorActionPreference = "Stop"
$deploy = $PSScriptRoot
$root = Split-Path -Parent $deploy
$dist = Join-Path $deploy "dist-control"
$serverDir = Join-Path $root "server"

Write-Host "Cai dat PyInstaller + dependencies (chi server)..."
pip install -q -r "$deploy\requirements-build.txt"
pip install -q -r "$root\server\requirements.txt"

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    throw "pyinstaller khong tim thay sau khi cai dat"
}

New-Item -ItemType Directory -Force -Path $dist | Out-Null
$specDir = Join-Path $deploy "control-server"
New-Item -ItemType Directory -Force -Path $specDir | Out-Null

Set-Location $serverDir
Write-Host "Build monitoring-control-server.exe (co the lau vai phut)..."
pyinstaller --noconfirm --clean --onefile `
    --name monitoring-control-server `
    --distpath $dist `
    --workpath (Join-Path $deploy "build\control-server") `
    --specpath $specDir `
    --paths $serverDir `
    --hidden-import main `
    --collect-all uvicorn `
    --collect-all fastapi `
    --collect-all starlette `
    --collect-all pydantic `
    run_server.py

$tokenFile = Join-Path $dist "auth.token"
if (-not (Test-Path $tokenFile)) {
    $hex = python -c "import secrets; print(secrets.token_hex(32))"
    Set-Content -Path $tokenFile -Value $hex -Encoding ascii -NoNewline
    Add-Content -Path $tokenFile -Value "" -Encoding ascii
    Write-Host "Da tao auth.token trong dist-control."
}

Copy-Item -Force (Join-Path $serverDir "server.env.example") (Join-Path $dist "server.env.example")

Set-Location $deploy

Write-Host ""
Write-Host "Xong. Thu muc trien khai server: $dist"
Write-Host "  monitoring-control-server.exe  - chay, mo http://HOST:PORT/docs"
Write-Host "  auth.token                       - copy cung cap cho may chay agent (cung noi dung BEARER)"
Write-Host "  pc-monitor-client: mac dinh http://<ip>:8010/api/agent/data (dong bo PORT server .exe)"
