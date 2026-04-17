from __future__ import annotations

import platform
import socket
import sys
import time as time_mod
from typing import Any

import psutil

from . import config
from . import screen

_last_removable_mounts: set[str] = set()

# Bo qua khi quet REGISTERED_PROCESS_CHECK (giam nhieu nhieu tren Windows).
_WINDOWS_REGISTRY_SKIP: frozenset[str] = frozenset(
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
        "pc-monitor-client.exe",
        "python.exe",
        "pythonw.exe",
    }
)

_LINUX_REGISTRY_SKIP: frozenset[str] = frozenset(
    {
        "systemd",
        "systemd-journald",
        "systemd-udevd",
        "dbus-daemon",
        "kthreadd",
        "kswapd0",
        "rcu_preempt",
        "rcu_sched",
        "migration/0",
        "watchdog/0",
        "gnome-shell",
        "xorg",
    }
)

_DEFAULT_BROWSERS: frozenset[str] = frozenset(
    {
        "chrome.exe",
        "msedge.exe",
        "firefox.exe",
        "brave.exe",
        "opera.exe",
        "iexplore.exe",
        "waterfox.exe",
        "vivaldi.exe",
    }
)

_browser_fg: dict[str, Any] = {"key": None, "since": 0.0, "alerted": False}
_last_unregistered_sig: str | None = None

_last_net_io: tuple[int, int] | None = None
_last_net_wall: float = 0.0
_fg_interval_ts: float | None = None
_fg_interval_was_browser: bool = False
_browser_seconds_buffer: float = 0.0


def _browser_exe_set() -> set[str]:
    raw = config.BROWSER_PROCESS_NAMES_RAW
    if raw:
        return {x.strip().lower() for x in raw.split(",") if x.strip()}
    return set(_DEFAULT_BROWSERS)


def allowed_process_names() -> set[str] | None:
    if not config.ALLOWED_RAW:
        return None
    return {x.strip().lower() for x in config.ALLOWED_RAW.split(",") if x.strip()}


def get_system_info() -> dict[str, Any]:
    mem = psutil.virtual_memory()
    disk_usage: dict[str, float] = {}
    for dp in psutil.disk_partitions(all=False):
        if "cdrom" in dp.opts.lower():
            continue
        try:
            disk_usage[dp.mountpoint] = psutil.disk_usage(dp.mountpoint).percent
        except (PermissionError, OSError):
            continue
    return {
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "os_version": platform.version(),
        "cpu_count": psutil.cpu_count(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_total": mem.total,
        "memory_used": mem.used,
        "memory_percent": mem.percent,
        "disk_usage": disk_usage,
    }


def get_top_processes(n: int = 10) -> list[dict[str, Any]]:
    procs = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time_mod.sleep(1)
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    out: list[dict[str, Any]] = []
    for p in sorted(procs, key=lambda x: x.info.get("cpu_percent") or 0, reverse=True)[:n]:
        try:
            out.append(
                {
                    "pid": p.info["pid"],
                    "name": p.info["name"],
                    "cpu_percent": p.info["cpu_percent"],
                    "memory_percent": p.info["memory_percent"],
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
            continue
    return out


def get_network_connections() -> list[dict[str, Any]]:
    conns: list[dict[str, Any]] = []
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.status != psutil.CONN_ESTABLISHED:
                continue
            la = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None
            ra = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None
            conns.append({"local_addr": la, "remote_addr": ra, "pid": conn.pid})
    except (psutil.AccessDenied, PermissionError):
        pass
    return conns[:50]


def _removable_mounts() -> set[str]:
    found: set[str] = set()
    for dp in psutil.disk_partitions(all=True):
        opts = dp.opts.lower()
        if "removable" in opts or "usb" in getattr(dp, "device", "").lower():
            found.add(dp.mountpoint)
    return found


def usb_events() -> list[dict[str, Any]]:
    global _last_removable_mounts
    if not config.DETECT_USB:
        return []
    current = _removable_mounts()
    added = current - _last_removable_mounts
    removed = _last_removable_mounts - current
    _last_removable_mounts = current
    events: list[dict[str, Any]] = []
    for m in added:
        events.append({"type": "removable_mounted", "mountpoint": m})
    for m in removed:
        events.append({"type": "removable_unmounted", "mountpoint": m})
    return events


def registered_process_events() -> list[dict[str, Any]]:
    """Process dang chay khong co trong ALLOWED_PROCESS_NAMES (can REGISTERED_PROCESS_CHECK=1)."""
    global _last_unregistered_sig
    if not config.REGISTERED_PROCESS_CHECK:
        return []
    allow = allowed_process_names()
    if not allow:
        return []
    pl = platform.system().lower()
    if "windows" in pl:
        skip = _WINDOWS_REGISTRY_SKIP
    elif "linux" in pl:
        skip = _LINUX_REGISTRY_SKIP
    else:
        skip = frozenset()
    names_seen: set[str] = set()
    try:
        for p in psutil.process_iter(["name"]):
            try:
                n = (p.info.get("name") or "").lower()
                if n:
                    names_seen.add(n)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        return []
    bad = sorted(m for m in names_seen if m not in allow and m not in skip)
    if not bad:
        _last_unregistered_sig = None
        return []
    sig = "|".join(bad)
    if sig == _last_unregistered_sig:
        return []
    _last_unregistered_sig = sig
    cap = 40
    total = len(bad)
    sample = bad[:cap]
    return [
        {
            "type": "unregistered_software",
            "processes": sample,
            "total_count": total,
            "truncated": total > cap,
        }
    ]


def foreground_browser_events() -> list[dict[str, Any]]:
    """Canh bao trinh duyet giu foreground qua lau (Windows)."""
    global _browser_fg
    if config.LONG_BROWSER_ALERT_SECONDS <= 0 or sys.platform != "win32":
        return []
    try:
        from .win_foreground import foreground_process_title
    except Exception:
        return []
    ft = foreground_process_title()
    if not ft:
        return []
    exe, title = ft
    if exe not in _browser_exe_set():
        _browser_fg = {"key": None, "since": 0.0, "alerted": False}
        return []
    key = (exe, (title or "")[:200])
    now = time_mod.time()
    if _browser_fg.get("key") != key:
        _browser_fg = {"key": key, "since": now, "alerted": False}
        return []
    dur = now - float(_browser_fg["since"])
    if dur >= float(config.LONG_BROWSER_ALERT_SECONDS) and not _browser_fg.get("alerted"):
        _browser_fg["alerted"] = True
        return [
            {
                "type": "long_browser_session",
                "exe": exe,
                "title": (title or "")[:240],
                "seconds_foreground": int(dur),
            }
        ]
    return []


def collect_network_io_delta() -> dict[str, Any] | None:
    """Byte gui/nhan giua lan goi nay va lan truoc (tat ca NIC). Lan dau: chi tao baseline."""
    global _last_net_io, _last_net_wall
    if not config.TRACK_NETWORK_IO:
        return None
    now = time_mod.time()
    try:
        io = psutil.net_io_counters(pernic=False)
    except Exception:
        return None
    sent, recv = int(io.bytes_sent), int(io.bytes_recv)
    if _last_net_io is None:
        _last_net_io = (sent, recv)
        _last_net_wall = now
        return None
    prev_s, prev_r = _last_net_io
    dt = max(1e-6, now - _last_net_wall)
    ds = sent - prev_s
    dr = recv - prev_r
    if ds < 0:
        ds = 0
    if dr < 0:
        dr = 0
    _last_net_io = (sent, recv)
    _last_net_wall = now
    return {
        "bytes_sent": ds,
        "bytes_recv": dr,
        "interval_seconds": round(dt, 2),
        "note": "Tổng mọi giao diện mạng trên máy; không phân tách từng website.",
    }


def collect_browser_foreground_interval() -> dict[str, Any] | None:
    """Giay (tich luy) cua so trinh duyet foreground giua hai lan goi ham (Windows)."""
    global _fg_interval_ts, _fg_interval_was_browser, _browser_seconds_buffer
    if not config.TRACK_BROWSER_FOREGROUND:
        return None
    now = time_mod.time()
    if sys.platform != "win32":
        return {
            "interval_seconds": 0.0,
            "note": "Chỉ hỗ trợ Windows (cửa sổ foreground).",
        }

    is_browser = False
    try:
        from .win_foreground import foreground_process_title

        ft = foreground_process_title()
        if ft:
            is_browser = ft[0] in _browser_exe_set()
    except Exception:
        pass

    if _fg_interval_ts is not None:
        dt = now - float(_fg_interval_ts)
        if dt > 0 and _fg_interval_was_browser:
            _browser_seconds_buffer += dt
    _fg_interval_ts = now
    _fg_interval_was_browser = is_browser

    out_sec = round(_browser_seconds_buffer, 2)
    _browser_seconds_buffer = 0.0
    return {
        "interval_seconds": out_sec,
        "note": "Trình duyệt đang focus; không phải URL hay byte từng site.",
    }


def enforce_allowlist_on_processes(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allow = allowed_process_names()
    if not allow or not config.ENFORCE_ALLOWLIST:
        return []
    killed: list[dict[str, Any]] = []
    for row in processes:
        name = (row.get("name") or "").lower()
        if not name or name in allow:
            continue
        pid = row.get("pid")
        if pid is None:
            continue
        try:
            p = psutil.Process(int(pid))
            p.terminate()
            try:
                p.wait(timeout=3)
            except psutil.TimeoutExpired:
                p.kill()
            killed.append({"pid": pid, "name": row.get("name"), "action": "terminated"})
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, TypeError) as e:
            killed.append({"pid": pid, "name": row.get("name"), "action": "error", "error": str(e)})
    return killed


def build_payload(cycle: int | None = None) -> dict[str, Any]:
    # Chup man hinh ngay dau chu ky (tranh tre sau do psutil cho ~2s)
    screen_data = screen.capture_screen_jpeg_b64(cycle=cycle)
    top = get_top_processes(10)
    allow = allowed_process_names()
    nio = collect_network_io_delta()
    bf = collect_browser_foreground_interval()
    ev = usb_events()
    ev.extend(registered_process_events())
    ev.extend(foreground_browser_events())
    if nio and config.NETWORK_ALERT_BYTES_PER_INTERVAL > 0:
        tot = int(nio.get("bytes_sent", 0)) + int(nio.get("bytes_recv", 0))
        if tot >= config.NETWORK_ALERT_BYTES_PER_INTERVAL:
            ev.append(
                {
                    "type": "high_network_usage",
                    "bytes_total": tot,
                    "bytes_sent": int(nio.get("bytes_sent", 0)),
                    "bytes_recv": int(nio.get("bytes_recv", 0)),
                    "interval_seconds": nio.get("interval_seconds"),
                }
            )
    payload: dict[str, Any] = {
        "agent_id": config.AGENT_ID,
        "timestamp": time_mod.time(),
        "system_info": get_system_info(),
        "top_processes": top,
        "network_connections": get_network_connections(),
        "events": ev,
    }
    if config.DEVICE_DISPLAY_NAME:
        payload["display_name"] = config.DEVICE_DISPLAY_NAME
    if nio:
        payload["network_io"] = nio
    if bf:
        payload["browser_foreground"] = bf
    if allow is not None:
        payload["process_allowlist"] = sorted(allow)
    actions = enforce_allowlist_on_processes(top)
    if actions:
        payload["enforcement_actions"] = actions
    payload.update(screen_data)
    if config.DNS_CACHE_DOMAINS and config.DNS_CACHE_DOMAIN_MAX > 0:
        try:
            from .win_dns_cache import collect_dns_cache_domains

            dd = collect_dns_cache_domains(max_domains=config.DNS_CACHE_DOMAIN_MAX)
            if dd:
                payload["dns_recent_domains"] = dd
                payload["dns_recent_domains_note"] = (
                    "Ten mien tu bo dem DNS Windows (phan giai gan day); khong phai URL day du; "
                    "khong dong nghia dang mo trang ngay bay gio."
                )
        except Exception:
            pass
    return payload
