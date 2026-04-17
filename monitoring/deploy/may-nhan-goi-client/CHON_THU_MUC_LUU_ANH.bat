@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PC Monitor - chon thu muc luu anh
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0chon_thu_muc_luu_anh.ps1"
echo.
pause
