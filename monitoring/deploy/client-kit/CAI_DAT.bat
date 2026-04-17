@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PC Monitor - cai dat may ngoai
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cai_dat.ps1"
echo.
pause
