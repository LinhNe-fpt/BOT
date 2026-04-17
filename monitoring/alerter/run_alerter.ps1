# Chạy: .\run_alerter.ps1
# Không dán ký tự ">>" từ terminal vào đây.

$env:MONITOR_DB_PATH = "c:\BOT\monitoring\server\monitor.db"

# Tùy chọn: allowlist ngắn — alerter tự gộp bỏ qua OS + (mặc định) python/cursor/code trên Windows
# $env:ALLOWED_PROCESS_NAMES = "explorer.exe,svchost.exe"
# Máy chỉ server, muốn cảnh báo cả python trên top CPU: bật dòng dưới
# $env:SKIP_DEV_PROCESS_IGNORE = "1"
# $env:EXTRA_IGNORE_PROCESS_NAMES = "ten_khac.exe"
# $env:ALERT_WEBHOOK_URL = "https://hooks.slack.com/..."

Set-Location $PSScriptRoot
python alerter.py
