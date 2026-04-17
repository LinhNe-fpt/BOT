"""
Bot chạy nền (không cửa sổ console) — dùng cho máy ngoài / triển khai client.
Build: PyInstaller --windowed → pc-monitor-client.exe
"""
from __future__ import annotations

import os

os.environ["SILENT_CLIENT"] = "1"

from pc_monitor_bot.app import main_silent

if __name__ == "__main__":
    main_silent()
