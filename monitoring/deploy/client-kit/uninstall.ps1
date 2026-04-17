# Go PC Monitor client: dung exe, go task tu dong, tuy chon xoa file cau hinh / exe.
# Neu agent.env co STOP_PASSWORD thi bat buoc nhap dung.
# Chay: UNINSTALL.bat  hoac  powershell -File uninstall.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "  === PC Monitor - go cai dat (uninstall) ===" -ForegroundColor Cyan
Write-Host "  Dung tien trinh, go task dang nhap, sau do tuy chon xoa file." -ForegroundColor DarkGray
Write-Host ""

$common = Join-Path $root "pc_monitor_client_common.ps1"
if (-not (Test-Path $common)) {
    Write-Host "Thieu file pc_monitor_client_common.ps1" -ForegroundColor Red
    exit 1
}
. $common

$ae = Join-Path $root "agent.env"
if (-not (Test-StopPasswordIfSet -EnvFilePath $ae)) {
    Write-Host "Dung lai." -ForegroundColor Red
    exit 1
}

$procs = Get-Process -Name "pc-monitor-client" -ErrorAction SilentlyContinue
if ($procs) {
    $procs | Stop-Process -Force
    Write-Host "[OK] Da dung tien trinh pc-monitor-client." -ForegroundColor Green
} else {
    Write-Host "[--] Khong thay pc-monitor-client dang chay." -ForegroundColor DarkGray
}

try {
    Unregister-PcMonitorScheduledTask
    Write-Host "[OK] Da go task '$($script:PcmTaskName)' (neu da tung dang ky)." -ForegroundColor Green
} catch {
    Write-Host "[!!] Loi go task: $_" -ForegroundColor Red
}

Write-Host ""
$ynCfg = Read-Host "Xoa file cau hinh (agent.env, auth.token, client_first_run.done, register_logon_task.done, client_last_error.txt)?  C = Co, K = Khong [C]"
if ($ynCfg -notmatch "^[kK]") {
    $cfgFiles = @(
        (Join-Path $root "agent.env"),
        (Join-Path $root "auth.token"),
        (Join-Path $root "client_first_run.done"),
        (Join-Path $root "register_logon_task.done"),
        (Join-Path $root "client_last_error.txt")
    )
    foreach ($p in $cfgFiles) {
        if (Test-Path $p) {
            try {
                Remove-Item -LiteralPath $p -Force
                Write-Host "  Da xoa: $(Split-Path $p -Leaf)" -ForegroundColor DarkGray
            } catch {
                Write-Host "  Khong xoa duoc: $p - $_" -ForegroundColor Yellow
            }
        }
    }
    Write-Host "[OK] Da xu ly xoa cau hinh (neu file ton tai)." -ForegroundColor Green
}

Write-Host ""
$exePath = Join-Path $root "pc-monitor-client.exe"
$ynExe = Read-Host "Xoa file pc-monitor-client.exe?  C = Co, K = Khong [K]"
if ($ynExe -match "^[cC]" -and (Test-Path $exePath)) {
    Start-Sleep -Milliseconds 400
    try {
        Remove-Item -LiteralPath $exePath -Force
        Write-Host "[OK] Da xoa pc-monitor-client.exe" -ForegroundColor Green
    } catch {
        Write-Host "[!!] Khong xoa duoc exe (co the van dang chay / quyen): $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Hoan tat go cai dat. Con lai: script .bat/.ps1, HUONG-DAN.txt - xoa thu muc tay neu can." -ForegroundColor Cyan
Write-Host ""
