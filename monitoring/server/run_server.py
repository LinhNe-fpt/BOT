"""
Chạy API ingest (dev hoặc bản .exe PyInstaller).
Dev: python run_server.py
EXE: BEARER_TOKEN qua biến môi trường hoặc file server.env cạnh .exe; DB mặc định cạnh .exe.
"""
from __future__ import annotations

import multiprocessing
import os
import sys
from pathlib import Path


def main() -> None:
    multiprocessing.freeze_support()
    exe_dir: Path | None = None
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        os.environ.setdefault("MONITOR_DB_PATH", str(exe_dir / "monitor.db"))
        if hasattr(sys, "_MEIPASS"):
            sys.path.insert(0, sys._MEIPASS)
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    # .exe mac dinh 8010 de tranh WinError 10048 (port 8000 thuong bi uvicorn/docker khac chiem)
    _port_default = "8010" if exe_dir is not None else "8000"
    port = int(os.environ.get("PORT", _port_default))
    if exe_dir is not None:
        print(
            "[monitoring-control-server] Nhan telemetry agent: POST /api/agent/data",
            file=sys.stderr,
        )
        print(
            f"[monitoring-control-server] http://{host}:{port}/  | admin: http://{host}:{port}/admin  | DB: {exe_dir / 'monitor.db'}",
            file=sys.stderr,
        )
        print(
            "[monitoring-control-server] Dung chung auth.token canh .exe voi pc-monitor-client. "
            f"Bot .exe mac dinh gui toi port {port}.",
            file=sys.stderr,
        )
    uvicorn.run("main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
