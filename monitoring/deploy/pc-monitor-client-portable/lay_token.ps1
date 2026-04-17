# Chay tren may client: hien token trong auth.token (cung thu muc pc-monitor-client.exe).
# Chuot phai -> Run with PowerShell, hoac chay LAY_TOKEN.bat

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$tf = Join-Path $here "auth.token"
if (-not (Test-Path $tf)) {
    Write-Host "Khong tim thay file auth.token trong:" $here
    Write-Host "Dat script nay cung thu muc voi auth.token va pc-monitor-client.exe."
    if ($Host.Name -eq "ConsoleHost") { Read-Host "Enter de dong" }
    exit 1
}

$tok = ""
foreach ($raw in Get-Content $tf -Encoding utf8 -ErrorAction SilentlyContinue) {
    $s = $raw.Trim()
    if (-not $s -or $s.StartsWith("#")) { continue }
    $tok = $s.Trim('"').Trim("'")
    break
}
if (-not $tok) {
    Write-Host "File auth.token trong nhung khong doc duoc token."
    if ($Host.Name -eq "ConsoleHost") { Read-Host "Enter de dong" }
    exit 1
}

Write-Host ""
Write-Host "========== TOKEN (may nay) =========="
Write-Host $tok
Write-Host "====================================="
Write-Host ""

try {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.Clipboard]::SetText($tok) | Out-Null
    Write-Host "Da copy token vao clipboard (Ctrl+V de dan)."
    [void][System.Windows.Forms.MessageBox]::Show(
        "Token may nay:`n`n$tok`n`nDa copy vao clipboard.",
        "PC Monitor - Token",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    )
} catch {
    Write-Host "(Khong mo duoc hop thoai GUI - chi hien token o tren.)"
    if ($Host.Name -eq "ConsoleHost") { Read-Host "Enter de dong" }
}
