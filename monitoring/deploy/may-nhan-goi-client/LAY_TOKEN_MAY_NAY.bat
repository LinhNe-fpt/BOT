@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Hien token trong auth.token tren MAY NAY (cung thu muc script)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0lay_token.ps1"
if errorlevel 1 pause
