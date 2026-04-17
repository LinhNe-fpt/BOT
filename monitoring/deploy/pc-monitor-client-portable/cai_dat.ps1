# Tro giup nguoi khong quen sua file: nhap IP may chu, ghi agent.env, kiem tra auth.token.
# Chay bang: CAI_DAT.bat  hoac  powershell -File cai_dat.ps1

param([string]$Ip = "")

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "  === PC Monitor - cau hinh may nay gui ve MAY CHU ===" -ForegroundColor Cyan
Write-Host "  (Nhap IP cua MAY CHU = may chay monitoring-server. KHONG nhap IP may ban dang ngoi.)" -ForegroundColor DarkGray
Write-Host ""

if (-not $Ip) {
    $Ip = Read-Host "IP MAY CHU / server (may nhan du lieu, vi du 192.168.1.50)"
}
$Ip = ($Ip -replace "^\s+|\s+$", "") -replace "^https?://", "" -replace ":8010$", "" -replace "/.*$", ""
if (-not $Ip) {
    Write-Host "Chua nhap IP." -ForegroundColor Red
    exit 1
}

$base = "http://${Ip}:8010"
$full = "${base}/api/agent/data"
$ae = Join-Path $root "agent.env"

if (-not (Test-Path $ae)) {
    Write-Host "Khong tim thay agent.env trong thu muc nay." -ForegroundColor Red
    exit 1
}

$enc = New-Object System.Text.UTF8Encoding $false
$txt = [System.IO.File]::ReadAllText($ae, $enc)

if ($txt -match "(?m)^MONITOR_BASE_URL=") {
    $txt = [regex]::Replace($txt, "(?m)^MONITOR_BASE_URL=.*$", "MONITOR_BASE_URL=$base")
} else {
    $txt = "MONITOR_BASE_URL=$base`r`n" + $txt
}

# Luon ghi API_URL (neu thieu, exe cu chi doc default 127.0.0.1)
if ($txt -match "(?m)^API_URL=") {
    $txt = [regex]::Replace($txt, "(?m)^API_URL=.*$", "API_URL=$full")
} else {
    $txt += "`r`nAPI_URL=$full`r`n"
}

[System.IO.File]::WriteAllText($ae, $txt, $enc)
Write-Host "Da ghi may chu: $base" -ForegroundColor Green
Write-Host "API_URL=$full" -ForegroundColor DarkGray
Write-Host ""

$tf = Join-Path $root "auth.token"
if (-not (Test-Path $tf)) {
    Write-Host "CHUA CO file auth.token !" -ForegroundColor Yellow
    Write-Host "Hay copy file auth.token tu may chu (canh monitoring-server.exe) vao thu muc:"
    Write-Host "  $root" -ForegroundColor White
    Write-Host ""
    exit 1
}

$tokLine = $null
foreach ($raw in Get-Content $tf -Encoding utf8) {
    $s = $raw.Trim()
    if ($s -and -not $s.StartsWith("#")) { $tokLine = $s; break }
}
if (-not $tokLine) {
    Write-Host "File auth.token trong hoac khong hop le." -ForegroundColor Red
    exit 1
}

Write-Host "OK: da co auth.token" -ForegroundColor Green
Write-Host ""
$yn = Read-Host "Chay pc-monitor-client ngay (chay nen)?  C = Co, K = Khong [C]"
if ($yn -match "^[kK]") {
    Write-Host "Xong. Sau nay chi can chay pc-monitor-client.exe"
    exit 0
}

$exe = Join-Path $root "pc-monitor-client.exe"
if (-not (Test-Path $exe)) {
    Write-Host "Khong tim thay pc-monitor-client.exe" -ForegroundColor Red
    exit 1
}
Start-Process -FilePath $exe -WorkingDirectory $root
Write-Host "Da khoi dong pc-monitor-client (nen)." -ForegroundColor Green
