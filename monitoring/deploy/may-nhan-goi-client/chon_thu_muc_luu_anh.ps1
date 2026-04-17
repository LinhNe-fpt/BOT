# Chon thu muc luu anh man hinh moi lan chup -> ghi SCREEN_SAVE_DIR vao agent.env
# Chay: CHON_THU_MUC_LUU_ANH.bat

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$ae = Join-Path $root "agent.env"
if (-not (Test-Path $ae)) {
    Write-Host "Khong tim thay agent.env trong thu muc nay." -ForegroundColor Red
    exit 1
}

Add-Type -AssemblyName System.Windows.Forms | Out-Null
$dlg = New-Object System.Windows.Forms.FolderBrowserDialog
$dlg.Description = "Chon thu muc luu anh man hinh (moi lan chup se ghi file vao day)"
$dlg.ShowNewFolderButton = $true
$r = $dlg.ShowDialog()
if ($r -ne [System.Windows.Forms.DialogResult]::OK) {
    Write-Host "Da huy." -ForegroundColor DarkGray
    exit 0
}
$path = $dlg.SelectedPath
if (-not $path) { exit 1 }

$lines = @(Get-Content -LiteralPath $ae -Encoding utf8)
$out = New-Object System.Collections.Generic.List[string]
$found = $false
foreach ($line in $lines) {
    if ($line -match '^\s*SCREEN_SAVE_DIR=') {
        $out.Add("SCREEN_SAVE_DIR=$path")
        $found = $true
    } else {
        $out.Add($line)
    }
}
if (-not $found) {
    $out.Add("SCREEN_SAVE_DIR=$path")
}

$enc = New-Object System.Text.UTF8Encoding $false
$text = ($out -join "`r`n")
[System.IO.File]::WriteAllText($ae, $text, $enc)

Write-Host "Da ghi SCREEN_SAVE_DIR vao agent.env:" -ForegroundColor Green
Write-Host "  $path" -ForegroundColor White
Write-Host "Khoi dong lai pc-monitor-client.exe de ap dung." -ForegroundColor Cyan
