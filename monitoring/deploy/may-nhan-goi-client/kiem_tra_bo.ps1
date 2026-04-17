# Kiem tra du thanh phan truoc khi chay. Chay: powershell -File kiem_tra_bo.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$script:ok = $true
function Test-One($name, $path) {
    if (Test-Path $path) { Write-Host "[OK] $name" -ForegroundColor Green }
    else { Write-Host "[THIEU] $name" -ForegroundColor Red; $script:ok = $false }
}

Write-Host "Kiem tra bo trong: $root" -ForegroundColor Cyan
Test-One "pc-monitor-client.exe" (Join-Path $root "pc-monitor-client.exe")
Test-One "agent.env" (Join-Path $root "agent.env")
Test-One "auth.token" (Join-Path $root "auth.token")
Test-One "CAI_DAT.bat" (Join-Path $root "CAI_DAT.bat")
Test-One "cai_dat.ps1" (Join-Path $root "cai_dat.ps1")
Test-One "pc_monitor_client_common.ps1" (Join-Path $root "pc_monitor_client_common.ps1")
Test-One "TAT_CLIENT.bat" (Join-Path $root "TAT_CLIENT.bat")
Test-One "tat_client.ps1" (Join-Path $root "tat_client.ps1")
Test-One "UNINSTALL.bat" (Join-Path $root "UNINSTALL.bat")
Test-One "uninstall.ps1" (Join-Path $root "uninstall.ps1")
Test-One "lay_token.ps1" (Join-Path $root "lay_token.ps1")
Test-One "LAY_TOKEN_MAY_NAY.bat" (Join-Path $root "LAY_TOKEN_MAY_NAY.bat")
Test-One "GOI_GOM_THANH_PHAN.txt" (Join-Path $root "GOI_GOM_THANH_PHAN.txt")

if (-not (Test-Path (Join-Path $root "auth.token"))) {
    Write-Host "`nChua co auth.token - copy tu may chu vao thu muc nay." -ForegroundColor Yellow
    $script:ok = $false
} else {
    $t = Get-Content (Join-Path $root "auth.token") -Encoding utf8 -Raw
    if (-not $t.Trim()) { Write-Host "[TRONG] auth.token" -ForegroundColor Red; $script:ok = $false }
}

if ($script:ok) { Write-Host "`nDu dieu kien - chay CAI_DAT.bat neu chua cau hinh IP." -ForegroundColor Green }
else { Write-Host "`nThieu file - xem GOI_GOM_THANH_PHAN.txt" -ForegroundColor Red }
exit ($(if ($script:ok) { 0 } else { 1 }))
