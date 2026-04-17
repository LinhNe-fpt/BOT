@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PC Monitor - tat client
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tat_client.ps1"
echo.
pause
