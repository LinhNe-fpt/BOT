# Tao thu muc day du cho MAY NHAN GOI (client gui du lieu ve may chu).
# Chay tu deploy:  .\client-kit\tao_bo_cai_dat.ps1
#                  .\client-kit\tao_bo_cai_dat.ps1 -MonitorBaseUrl "http://192.168.6.64:8010"
#                  .\client-kit\tao_bo_cai_dat.ps1 -OutDir "D:\gui-khach"

param(
    [string]$DistPath = "",
    [string]$OutDir = "",
    [string]$MonitorBaseUrl = ""
)

$ErrorActionPreference = "Stop"
$kitRoot = $PSScriptRoot
$deploy = Split-Path -Parent $kitRoot
if (-not $DistPath) { $DistPath = Join-Path $deploy "dist" }
$DistPath = (Resolve-Path $DistPath).Path

$exe = Join-Path $DistPath "pc-monitor-client.exe"
if (-not (Test-Path $exe)) {
    throw "Khong tim thay pc-monitor-client.exe trong $DistPath - chay .\build_apps.ps1 -Agent truoc."
}

if (-not $OutDir) { $OutDir = Join-Path $deploy "may-nhan-goi-client" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Apply-BaseUrl-To-AgentEnv {
    param([string]$AgentEnvPath, [string]$RawBase)
    $b = $RawBase.Trim().TrimEnd("/")
    if (-not $b.StartsWith("http")) { $b = "http://$b" }
    $full = "$b/api/agent/data"
    $enc = New-Object System.Text.UTF8Encoding $false
    $txt = [System.IO.File]::ReadAllText($AgentEnvPath, $enc)
    if ($txt -match "(?m)^MONITOR_BASE_URL=") {
        $txt = [regex]::Replace($txt, "(?m)^MONITOR_BASE_URL=.*$", "MONITOR_BASE_URL=$b")
    } else {
        $txt = "MONITOR_BASE_URL=$b`r`n" + $txt
    }
    if ($txt -match "(?m)^API_URL=") {
        $txt = [regex]::Replace($txt, "(?m)^API_URL=.*$", "API_URL=$full")
    } else {
        $txt += "`r`nAPI_URL=$full`r`n"
    }
    [System.IO.File]::WriteAllText($AgentEnvPath, $txt, $enc)
}

$copyNames = @(
    "agent.env.template",
    "HUONG-DAN.txt",
    "lay_token.ps1",
    "LAY_TOKEN.bat",
    "LAY_TOKEN_MAY_NAY.bat",
    "pc_monitor_client_common.ps1",
    "cai_dat.ps1",
    "CAI_DAT.bat",
    "tat_client.ps1",
    "TAT_CLIENT.bat",
    "uninstall.ps1",
    "UNINSTALL.bat",
    "chon_thu_muc_luu_anh.ps1",
    "CHON_THU_MUC_LUU_ANH.bat",
    "GOI_GOM_THANH_PHAN.txt",
    "BAT_DAU_O_DAY.txt",
    "kiem_tra_bo.ps1",
    "KIEM_TRA.bat",
    "COPY_AUTH_TOKEN_TU_MAY_CHU.txt"
)
foreach ($n in $copyNames) {
    $p = Join-Path $kitRoot $n
    if (Test-Path $p) { Copy-Item $p $OutDir -Force }
}

Copy-Item $exe $OutDir -Force
Copy-Item (Join-Path $kitRoot "agent.env.template") (Join-Path $OutDir "agent.env") -Force

if ($MonitorBaseUrl) {
    Apply-BaseUrl-To-AgentEnv -AgentEnvPath (Join-Path $OutDir "agent.env") -RawBase $MonitorBaseUrl
    Write-Host "Da ghi MONITOR_BASE_URL + API_URL tu -MonitorBaseUrl" -ForegroundColor Green
}

$tokenSrc = Join-Path $DistPath "auth.token"
$tokenDst = Join-Path $OutDir "auth.token"
if (Test-Path $tokenSrc) {
    Copy-Item $tokenSrc $tokenDst -Force
    Write-Host "Da copy auth.token tu dist (cung token voi server)." -ForegroundColor Green
} else {
    Write-Host "Canh bao: khong co auth.token trong dist - xem COPY_AUTH_TOKEN_TU_MAY_CHU.txt trong bo." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Bo day du tai: $OutDir" -ForegroundColor Cyan
Write-Host "  - Doc BAT_DAU_O_DAY.txt hoac GOI_GOM_THANH_PHAN.txt"
Write-Host '  - May nhan goi: CAI_DAT.bat + auth.token + LAY_TOKEN_MAY_NAY.bat (lay token tren may do)'
Write-Host "Zip ca thu muc may-nhan-goi-client roi gui."
