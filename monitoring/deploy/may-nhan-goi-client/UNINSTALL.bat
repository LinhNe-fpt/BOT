@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PC Monitor - go cai dat
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
echo.
pause
