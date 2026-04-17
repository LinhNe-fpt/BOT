# Tuong hop: goi build_apps.ps1 -Agent
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "build_apps.ps1") -Agent
