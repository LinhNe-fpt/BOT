from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse


def app_dir() -> Path:
    if getattr(sys, "frozen", False) and getattr(sys, "executable", None):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        # agent.env canh .exe ghi de bien moi truong (tranh API_URL=127.0.0.1 thua ke tu shell cu)
        if key:
            os.environ[key] = val


TOKEN_FILE = "auth.token"


def token_file_path() -> Path:
    raw = (os.environ.get("AUTH_TOKEN_PATH") or "").strip()
    if raw:
        return Path(raw)
    return app_dir() / TOKEN_FILE


def read_shared_token(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                return s
    except OSError:
        return None
    return None


def resolve_secret_token() -> str:
    env = (os.environ.get("SECRET_TOKEN") or "").strip()
    if env and env != "change-me":
        return env
    t = read_shared_token(token_file_path())
    if t:
        return t
    return "change-me"


load_env_file(app_dir() / "agent.env")

# SILENT_CLIENT=1: khong in stderr / chay nen (entry silent_bot + exe windowed)
SILENT_CLIENT = os.environ.get("SILENT_CLIENT", "0").strip().lower() in ("1", "true", "yes")

# Phai dong bo voi run_server.py: .exe mac dinh 8010 (tranh dung port 8000 voi service khac)
_frozen = getattr(sys, "frozen", False)
_default_api = (
    "http://127.0.0.1:8010/api/agent/data"
    if _frozen
    else "http://127.0.0.1:8000/api/agent/data"
)
# API_URL day du HOAC chi MONITOR_BASE_URL=http://IP:8010 (tu noi thanh .../api/agent/data)
_api_raw = (os.environ.get("API_URL") or "").strip()
_base = (os.environ.get("MONITOR_BASE_URL") or os.environ.get("SERVER_URL") or "").strip()
if _api_raw:
    API_URL = _api_raw
elif _base:
    API_URL = f"{_base.rstrip('/')}/api/agent/data"
else:
    API_URL = _default_api
AGENT_ID = (os.environ.get("AGENT_ID") or "").strip() or socket.gethostname()
# Ten hien thi tren admin (tuy chon). Agent ID / hostname van dung de luu du lieu.
DEVICE_DISPLAY_NAME = (os.environ.get("DEVICE_DISPLAY_NAME") or "").strip()
# Windows + .exe: lan chay dau dang ky task chay khi dang nhap (khong can chay lai CAI_DAT).
REGISTER_LOGON_TASK = os.environ.get("REGISTER_LOGON_TASK", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)
SECRET_TOKEN = resolve_secret_token()
INTERVAL_SECONDS = max(5, int(os.environ.get("INTERVAL_SECONDS", "15")))
REQUEST_TIMEOUT = max(10, int(os.environ.get("REQUEST_TIMEOUT", "60")))
MAX_RETRIES = max(1, int(os.environ.get("MAX_RETRIES", "5")))
RETRY_BACKOFF_BASE = max(1.5, float(os.environ.get("RETRY_BACKOFF_BASE", "2")))
_CACHE = os.environ.get("CACHE_DIR", "").strip()
CACHE_DIR = Path(_CACHE) if _CACHE else app_dir() / "outbox"
ALLOWED_RAW = os.environ.get("ALLOWED_PROCESS_NAMES", "").strip()
ENFORCE_ALLOWLIST = os.environ.get("ENFORCE_PROCESS_ALLOWLIST", "0").strip() in ("1", "true", "True", "yes")
DETECT_USB = os.environ.get("DETECT_USB", "1").strip() in ("1", "true", "True", "yes")
# REGISTERED_PROCESS_CHECK=1 + ALLOWED_PROCESS_NAMES: quet tat ca process, bao cao exe khong nam trong danh sach (su kien trong payload).
REGISTERED_PROCESS_CHECK = os.environ.get("REGISTERED_PROCESS_CHECK", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)
# Thoi gian (giay) cua so trinh duyet la foreground lien tuc truoc khi tao su kien canh bao (Windows). 0 = tat.
_lb = (os.environ.get("LONG_BROWSER_ALERT_SECONDS") or "").strip()
try:
    LONG_BROWSER_ALERT_SECONDS = int(_lb) if _lb else 0
except ValueError:
    LONG_BROWSER_ALERT_SECONDS = 0
# Ten process trinh duyet (phay). Mac dinh bo trong = dung danh co san.
_braw = (os.environ.get("BROWSER_PROCESS_NAMES") or "").strip()
BROWSER_PROCESS_NAMES_RAW = _braw
# Windows: doc danh sach ten mien tu Get-DnsClientCache (thu dong). 0 = tat.
DNS_CACHE_DOMAINS = os.environ.get("DNS_CACHE_DOMAINS", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)
_dcm = (os.environ.get("DNS_CACHE_DOMAIN_MAX") or "120").strip()
try:
    DNS_CACHE_DOMAIN_MAX = max(0, min(int(_dcm), 500))
except ValueError:
    DNS_CACHE_DOMAIN_MAX = 120
# Tong byte gui/nhan giua hai lan gui payload (tat ca NIC; khong tach theo website).
TRACK_NETWORK_IO = os.environ.get("TRACK_NETWORK_IO", "1").strip().lower() in (
    "1",
    "true",
    "yes",
)
# Thoi gian (giay) trong chu ky ma cua so trinh duyet la foreground (Windows).
TRACK_BROWSER_FOREGROUND = os.environ.get("TRACK_BROWSER_FOREGROUND", "1").strip().lower() in (
    "1",
    "true",
    "yes",
)
_nab = (os.environ.get("NETWORK_ALERT_BYTES_PER_INTERVAL") or "0").strip()
try:
    NETWORK_ALERT_BYTES_PER_INTERVAL = max(0, int(_nab))
except ValueError:
    NETWORK_ALERT_BYTES_PER_INTERVAL = 0
COMMAND_LISTENER = os.environ.get("COMMAND_LISTENER", "0").strip() in ("1", "true", "True", "yes")
COMMAND_LISTENER_PORT = int(os.environ.get("COMMAND_LISTENER_PORT", "18765"))
COMMAND_SECRET = os.environ.get("COMMAND_SECRET", "").strip()
SCREEN_CAPTURE = os.environ.get("SCREEN_CAPTURE", "1").strip().lower() in ("1", "true", "yes")
# Mac dinh 1600px ngang + chat luong 72: ro hon ban cu (960/55); co the giam neu bao loi anh qua lon.
SCREEN_MAX_WIDTH = max(320, min(int(os.environ.get("SCREEN_MAX_WIDTH", "1600")), 3840))
SCREEN_JPEG_QUALITY = max(30, min(int(os.environ.get("SCREEN_JPEG_QUALITY", "72")), 95))
try:
    SCREEN_MAX_B64_CHARS = max(200_000, min(int(os.environ.get("SCREEN_MAX_B64_CHARS", "1600000")), 4_000_000))
except ValueError:
    SCREEN_MAX_B64_CHARS = 1_600_000
# SCREEN_SAVE_LOCAL: 1 = ghi vao thu muc screenshots/ canh .exe. Mac dinh 0 = chi gui len server.
SCREEN_SAVE_LOCAL = os.environ.get("SCREEN_SAVE_LOCAL", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)
# SCREEN_SAVE_DIR: duong dan thu muc tuy chon — moi lan chup tu dong ghi file vao day (khong can SCREEN_SAVE_LOCAL).
# Uu tien hon SCREEN_SAVE_LOCAL. Vi du: SCREEN_SAVE_DIR=D:\PCMonitorScreens
SCREEN_SAVE_DIR = (os.environ.get("SCREEN_SAVE_DIR") or os.environ.get("SCREENSHOT_SAVE_DIR") or "").strip()
# SCREEN_KEEP_MAX: khi luu dia (LOCAL hoac SAVE_DIR). 0 = giu tat ca; >0 = chi giu N file screen_*.jpg moi nhat.
_keep_raw = (os.environ.get("SCREEN_KEEP_MAX") or os.environ.get("SCREEN_HISTORY_MAX") or "0").strip()
SCREEN_KEEP_MAX = max(0, int(_keep_raw))
# SCREEN_WRITE_LAST_FILE: chi khi SCREEN_SAVE_LOCAL=1 — ghi them screen_last.jpg (ghi de).
SCREEN_WRITE_LAST_FILE = os.environ.get("SCREEN_WRITE_LAST_FILE", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)


def reload_secret_if_file() -> None:
    global SECRET_TOKEN
    env = (os.environ.get("SECRET_TOKEN") or "").strip()
    if env and env != "change-me":
        return
    t = read_shared_token(token_file_path())
    if t:
        SECRET_TOKEN = t


def _api_url_placeholder_hint(url: str) -> str | None:
    """Chan agent.env de mac template THAY_BANG_IP_MAY_CHU (DNS that bai getaddrinfo)."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return None
    if "thay_bang_ip" in host or "thaybangip" in host.replace("_", ""):
        return (
            "Chua dat dia chi MAY CHU trong agent.env (van la chu mau THAY_BANG...).\n\n"
            "Sua mot trong hai cach:\n"
            "  MONITOR_BASE_URL=http://192.168.1.50:8010\n"
            "  hoac API_URL=http://192.168.1.50:8010/api/agent/data\n\n"
            "(IP = may chay monitoring-server, cung mang voi may nay.)"
        )
    return None


def validate_api_url() -> None:
    try:
        u = urlparse(API_URL)
        if not u.scheme or not u.netloc:
            raise ValueError("API_URL không hợp lệ")
        hint = _api_url_placeholder_hint(API_URL)
        if hint:
            raise ValueError(hint)
    except Exception as e:
        if SILENT_CLIENT and sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.MessageBoxW(0, str(e), "PC Monitor — API_URL lỗi", 0x10)
            except Exception:
                pass
        else:
            print(f"Cấu hình API_URL lỗi: {e}", file=sys.stderr)
        sys.exit(1)
