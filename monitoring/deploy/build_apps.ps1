# Đóng gói agent / alerter / server thành .exe (Windows) bằng PyInstaller.
# Chạy từ thư mục deploy:  .\build_apps.ps1
# Tùy chọn: .\build_apps.ps1 -Agent   hoặc -Alerter   hoặc -Server

param(
    [switch]$Agent,
    [switch]$Alerter,
    [switch]$Server
)

$ErrorActionPreference = "Stop"
$deploy = $PSScriptRoot
$root = Split-Path -Parent $deploy

$buildAll = -not ($Agent -or $Alerter -or $Server)
if ($buildAll) { $Agent = $Alerter = $Server = $true }

Write-Host "Cai dat PyInstaller + dependencies..."
pip install -q -r "$deploy\requirements-build.txt"
pip install -q -r "$root\agent\requirements.txt"
pip install -q -r "$root\alerter\requirements.txt"
pip install -q -r "$root\server\requirements.txt"

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    throw "pyinstaller khong tim thay sau khi cai dat"
}

$dist = Join-Path $deploy "dist"
New-Item -ItemType Directory -Force -Path $dist | Out-Null

if ($Agent) {
    Write-Host "Build pc-monitor-client.exe (may nhan: nen, khong console, hop thoai token lan dau) ..."
    Set-Location (Join-Path $root "agent")
    pyinstaller --noconfirm --clean --onefile --windowed `
        --name pc-monitor-client `
        --distpath $dist `
        --workpath (Join-Path $deploy "build\agent-client") `
        --specpath $deploy `
        --hidden-import command_listener `
        --collect-submodules pc_monitor_bot `
        --hidden-import PIL.ImageGrab `
        --hidden-import PIL.Image `
        silent_bot.py
}

if ($Alerter) {
    Write-Host "Build monitoring-alerter.exe ..."
    Set-Location (Join-Path $root "alerter")
    pyinstaller --noconfirm --clean --onefile `
        --name monitoring-alerter `
        --distpath $dist `
        --workpath (Join-Path $deploy "build\alerter") `
        --specpath $deploy `
        alerter.py
}

if ($Server) {
    Write-Host "Build monitoring-server.exe (co the lau vai phut) ..."
    $serverDir = Join-Path $root "server"
    Set-Location $serverDir
    $adminHtml = Join-Path $serverDir "admin_ui.html"
    $addData = @()
    if (Test-Path $adminHtml) {
        $addData += "--add-data"
        $addData += "${adminHtml};."
    }
    pyinstaller --noconfirm --clean --onefile `
        --name monitoring-server `
        --distpath $dist `
        --workpath (Join-Path $deploy "build\server") `
        --specpath $deploy `
        --paths $serverDir `
        --hidden-import main `
        --collect-all uvicorn `
        --collect-all fastapi `
        --collect-all starlette `
        --collect-all pydantic `
        @addData `
        run_server.py
}

Set-Location $deploy

$tokenFile = Join-Path $dist "auth.token"
if (-not (Test-Path $tokenFile)) {
    $hex = python -c "import secrets; print(secrets.token_hex(32))"
    Set-Content -Path $tokenFile -Value $hex -Encoding ascii -NoNewline
    Add-Content -Path $tokenFile -Value "" -Encoding ascii
    Write-Host "Da tao auth.token trong dist (agent + server doc chung file nay)."
}

Write-Host ""
Write-Host "Xong. File trong: $dist"
Write-Host "  auth.token             - chung cho agent + server neu khong dat BEARER_TOKEN/SECRET_TOKEN"
Write-Host "  pc-monitor-client.exe  - agent may nhan (nen); bo day du: .\client-kit\tao_bo_cai_dat.ps1"
Write-Host "  Bo may nhan goi:   .\client-kit\tao_bo_cai_dat.ps1  -> deploy\may-nhan-goi-client"
Write-Host "  (anh man hinh: screenshots/ hoac SCREEN_SAVE_DIR; SCREEN_KEEP_MAX=0 = khong xoa cu)"
Write-Host "  monitoring-alerter.exe - MONITOR_DB_PATH hoac monitor.db cung thu muc exe"
Write-Host "  monitoring-server.exe  - mac dinh PORT 8010; auth.token; monitor.db; /admin (UI may agent)"
Write-Host "  (chi server dieu khien: .\build_control_server.ps1 -> dist-control\monitoring-control-server.exe)"
