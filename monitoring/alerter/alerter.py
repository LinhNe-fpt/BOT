"""
Bot quét SQLite, phát hiện bất thường cơ bản, in log / gọi webhook.
Chạy định kỳ (cron / Task Scheduler) hoặc vòng lặp sleep.

Biến môi trường:
  MONITOR_DB_PATH — đường dẫn monitor.db (mặc định ../server/monitor.db)
  CPU_ALERT_PCT, MEM_ALERT_PCT — ngưỡng cảnh báo
  ALLOWED_PROCESS_NAMES — tên process được phép thêm (phẩy); chỉ dùng khi đặt
  PROCESS_ALLOWLIST_STRICT=1 — cảnh báo mọi process top không nằm trong danh sách này (ồn ào)
  Mặc định STRICT=0: gộp thêm bỏ qua OS (System Idle, dwm, MsMpEng, …) + ALLOWED
  EXTRA_IGNORE_PROCESS_NAMES — bỏ qua thêm (phẩy)
  SKIP_DEV_PROCESS_IGNORE=1 — trên Windows, không gộp bỏ qua python/cursor/code (máy chỉ server)
  IP_BLACKLIST — IP hoặc prefix (phẩy), khớp remote_addr
  ALERT_WEBHOOK_URL — POST JSON nếu có
  SCAN_INTERVAL_SECONDS — >0 để chạy lặp
  Su kien tu agent (trong data_json.events):
    removable_mounted -> usb_or_removable
    unregistered_software -> unregistered_software (khi agent REGISTERED_PROCESS_CHECK=1 + ALLOWED_PROCESS_NAMES)
    long_browser_session -> long_browser_session (Windows, agent LONG_BROWSER_ALERT_SECONDS > 0)
    high_network_usage -> high_network_usage (agent NETWORK_ALERT_BYTES_PER_INTERVAL > 0)
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import requests


def _default_monitor_db() -> Path:
    if getattr(sys, "frozen", False) and getattr(sys, "executable", None):
        return Path(sys.executable).resolve().parent / "monitor.db"
    return Path(__file__).resolve().parent.parent / "server" / "monitor.db"


DB_PATH = Path(os.environ.get("MONITOR_DB_PATH", _default_monitor_db()))
CPU_ALERT = float(os.environ.get("CPU_ALERT_PCT", "95"))
MEM_ALERT = float(os.environ.get("MEM_ALERT_PCT", "90"))
ALLOWED_RAW = os.environ.get("ALLOWED_PROCESS_NAMES", "").strip()
STRICT_ALLOWLIST = os.environ.get("PROCESS_ALLOWLIST_STRICT", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)
EXTRA_IGNORE_RAW = os.environ.get("EXTRA_IGNORE_PROCESS_NAMES", "").strip()
SKIP_DEV_PROCESS_IGNORE = os.environ.get("SKIP_DEV_PROCESS_IGNORE", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)
IP_BLACKLIST_RAW = os.environ.get("IP_BLACKLIST", "").strip()
WEBHOOK = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
INTERVAL = int(os.environ.get("SCAN_INTERVAL_SECONDS", "0"))


def allowed_names() -> set[str] | None:
    if not ALLOWED_RAW:
        return None
    return {x.strip().lower() for x in ALLOWED_RAW.split(",") if x.strip()}


def _builtin_ignored_os(os_name: str) -> frozenset[str]:
    n = (os_name or "").lower()
    if "windows" in n:
        return frozenset(
            {
                "system idle process",
                "system",
                "registry",
                "interrupts",
                "smss.exe",
                "csrss.exe",
                "wininit.exe",
                "services.exe",
                "lsass.exe",
                "svchost.exe",
                "fontdrvhost.exe",
                "winlogon.exe",
                "dwm.exe",
                "sihost.exe",
                "taskhostw.exe",
                "taskhost.exe",
                "explorer.exe",
                "runtimebroker.exe",
                "searchhost.exe",
                "searchindexer.exe",
                "msmpeng.exe",
                "nissrv.exe",
                "securityhealthservice.exe",
                "securityhealthsystray.exe",
                "audiodg.exe",
                "dllhost.exe",
                "conhost.exe",
                "mmc.exe",
                "spoolsv.exe",
                "sgrmbroker.exe",
                "ctfmon.exe",
                "phoneexperiencehost.exe",
                "applicationframehost.exe",
                "startmenuexperiencehost.exe",
                "shellhost.exe",
            }
        )
    if "linux" in n:
        return frozenset(
            {
                "systemd",
                "systemd-journald",
                "systemd-udevd",
                "dbus-daemon",
                "kthreadd",
                "ksoftirqd/0",
                "rcu_preempt",
                "rcu_sched",
                "migration/0",
                "watchdog/0",
                "kswapd0",
            }
        )
    if "darwin" in n:
        return frozenset(
            {
                "kernel_task",
                "launchd",
                "windowserver",
                "loginwindow",
                "mds",
                "mds_stores",
                "mdworker_shared",
            }
        )
    return frozenset()


# Khi có allowlist + không strict: bỏ qua thêm IDE/Python phổ biến (máy dev). Tắt: SKIP_DEV_PROCESS_IGNORE=1
_WINDOWS_DEV_PROCS = frozenset(
    {
        "python.exe",
        "pythonw.exe",
        "cursor.exe",
        "code.exe",
        "devenv.exe",
        "wt.exe",
        "windowsterminal.exe",
    }
)


def effective_process_ignore(sysinfo: dict) -> set[str] | None:
    """Nếu không có ALLOWED_PROCESS_NAMES thì không kiểm tra unknown_process."""
    user_allow = allowed_names()
    if user_allow is None:
        return None
    out: set[str] = set(user_allow)
    if EXTRA_IGNORE_RAW:
        out |= {x.strip().lower() for x in EXTRA_IGNORE_RAW.split(",") if x.strip()}
    if not STRICT_ALLOWLIST:
        osn = str(sysinfo.get("os") or "").lower()
        out |= _builtin_ignored_os(osn)
        if "windows" in osn and not SKIP_DEV_PROCESS_IGNORE:
            out |= _WINDOWS_DEV_PROCS
    return out


def ip_blacklist() -> list[str]:
    if not IP_BLACKLIST_RAW:
        return []
    return [x.strip() for x in IP_BLACKLIST_RAW.split(",") if x.strip()]


def latest_rows_per_agent(limit_agents: int = 50) -> list[tuple[str, float, str]]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT agent_id, timestamp, data_json FROM agent_data
            WHERE id IN (
                SELECT MAX(id) FROM agent_data GROUP BY agent_id LIMIT ?
            )
            """,
            (limit_agents,),
        )
        return c.fetchall()
    finally:
        conn.close()


def analyze_row(agent_id: str, ts: float, data_json: str) -> list[dict]:
    alerts: list[dict] = []
    try:
        data = json.loads(data_json)
    except json.JSONDecodeError:
        return [{"type": "parse_error", "agent_id": agent_id, "timestamp": ts}]

    sysinfo = data.get("system_info") or {}
    cpu = sysinfo.get("cpu_percent")
    mem = sysinfo.get("memory_percent")
    if cpu is not None and float(cpu) >= CPU_ALERT:
        alerts.append(
            {
                "type": "high_cpu",
                "agent_id": agent_id,
                "timestamp": ts,
                "cpu_percent": cpu,
            }
        )
    if mem is not None and float(mem) >= MEM_ALERT:
        alerts.append(
            {
                "type": "high_memory",
                "agent_id": agent_id,
                "timestamp": ts,
                "memory_percent": mem,
            }
        )

    ignore = effective_process_ignore(sysinfo)
    if ignore is not None:
        for p in data.get("top_processes") or []:
            name = (p.get("name") or "").lower()
            if name and name not in ignore:
                alerts.append(
                    {
                        "type": "unknown_process",
                        "agent_id": agent_id,
                        "timestamp": ts,
                        "process": p,
                    }
                )

    bl = ip_blacklist()
    if bl:
        for c in data.get("network_connections") or []:
            remote = c.get("remote_addr") or ""
            if not remote:
                continue
            ip = remote.split(":")[0]
            for bad in bl:
                if ip == bad or ip.startswith(bad):
                    alerts.append(
                        {
                            "type": "blacklisted_connection",
                            "agent_id": agent_id,
                            "timestamp": ts,
                            "connection": c,
                            "matched": bad,
                        }
                    )

    for ev in data.get("events") or []:
        et = ev.get("type")
        if et == "removable_mounted":
            alerts.append(
                {
                    "type": "usb_or_removable",
                    "agent_id": agent_id,
                    "timestamp": ts,
                    "event": ev,
                }
            )
        elif et == "unregistered_software":
            alerts.append(
                {
                    "type": "unregistered_software",
                    "agent_id": agent_id,
                    "timestamp": ts,
                    "processes": ev.get("processes"),
                    "total_count": ev.get("total_count"),
                    "truncated": ev.get("truncated"),
                }
            )
        elif et == "long_browser_session":
            alerts.append(
                {
                    "type": "long_browser_session",
                    "agent_id": agent_id,
                    "timestamp": ts,
                    "exe": ev.get("exe"),
                    "title": ev.get("title"),
                    "seconds_foreground": ev.get("seconds_foreground"),
                }
            )
        elif et == "high_network_usage":
            alerts.append(
                {
                    "type": "high_network_usage",
                    "agent_id": agent_id,
                    "timestamp": ts,
                    "bytes_total": ev.get("bytes_total"),
                    "bytes_sent": ev.get("bytes_sent"),
                    "bytes_recv": ev.get("bytes_recv"),
                    "interval_seconds": ev.get("interval_seconds"),
                }
            )

    return alerts


def send_webhook(alerts: list[dict]) -> None:
    if not WEBHOOK or not alerts:
        return
    try:
        r = requests.post(WEBHOOK, json={"alerts": alerts}, timeout=15)
        if r.status_code >= 400:
            print(f"Webhook lỗi HTTP {r.status_code}", file=sys.stderr)
    except requests.RequestException as e:
        print(f"Webhook thất bại: {e}", file=sys.stderr)


def run_once() -> int:
    rows = latest_rows_per_agent()
    all_alerts: list[dict] = []
    for agent_id, ts, blob in rows:
        all_alerts.extend(analyze_row(agent_id, ts, blob))
    for a in all_alerts:
        print(json.dumps(a, ensure_ascii=False))
    send_webhook(all_alerts)
    return len(all_alerts)


def main() -> None:
    if INTERVAL > 0:
        while True:
            run_once()
            time.sleep(INTERVAL)
    else:
        n = run_once()
        sys.exit(0 if n == 0 else 1)


if __name__ == "__main__":
    main()
