"""
Windows: doc ten mien tu bo dem DNS client (Get-DnsClientCache) — thu dong, khong ket noi toi cac site.
Day la cac ten da duoc phan giai gan day, khong dong nghia 'dang mo tab' ngay luc do.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


def collect_dns_cache_domains(*, max_domains: int) -> list[str]:
    if sys.platform != "win32" or max_domains <= 0:
        return []
    system_root = os.environ.get("SystemRoot") or os.environ.get("SYSTEMROOT") or r"C:\Windows"
    ps_exe = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    cmd = str(ps_exe) if ps_exe.is_file() else "powershell"
    # Entry = ten mien hoac doi khi dang PTR/IP — loc sau
    ps_script = (
        "Get-DnsClientCache | Where-Object { $_.Entry } "
        "| Select-Object -ExpandProperty Entry | Sort-Object -Unique"
    )
    try:
        r = subprocess.run(
            [cmd, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return []
    if r.returncode != 0:
        return []
    ip_v4 = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
    seen: set[str] = set()
    for line in r.stdout.splitlines():
        s = line.strip().lower().rstrip(".")
        if not s or len(s) > 253:
            continue
        if s in ("localhost", "::1", "0.0.0.0"):
            continue
        if ip_v4.match(s):
            continue
        if ".arpa" in s or s.endswith(".ip6.arpa"):
            continue
        if s.endswith(".local") and s.count(".") <= 1:
            continue
        seen.add(s)
    return sorted(seen)[:max_domains]
