# Dung pc-monitor-client + (tuy chon) go task tu dong khi dang nhap.
# Neu agent.env co STOP_PASSWORD thi bat buoc nhap dung moi tiep tuc.
# Chay: TAT_CLIENT.bat  hoac  powershell -File tat_client.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

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
    Write-Host "Da dung tien trinh pc-monitor-client." -ForegroundColor Green
} else {
    Write-Host "Khong thay pc-monitor-client dang chay." -ForegroundColor DarkGray
}

Write-Host ""
$yn = Read-Host "Go task tu dong khi dang nhap ($($script:PcmTaskName))?  C = Co, K = Khong [K]"
if ($yn -match "^[cC]") {
    try {
        Unregister-PcMonitorScheduledTask
        Write-Host "Da go task '$($script:PcmTaskName)'." -ForegroundColor Green
    } catch {
        Write-Host "Loi go task: $_" -ForegroundColor Red
        exit 1
    }
}
Write-Host "Xong." -ForegroundColor Green
