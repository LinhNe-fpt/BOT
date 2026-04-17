"""
Server trung tâm nhận dữ liệu agent (FastAPI + SQLite).
Chạy: uvicorn main:app --host 0.0.0.0 --port 8000
Biến môi trường: BEARER_TOKEN, ADMIN_TOKEN (tùy chọn), MONITOR_DB_PATH, AUTH_TOKEN_PATH, CAPTURES_DIR
Admin: GET /admin + GET /api/admin/agents (Bearer = ADMIN_TOKEN hoặc BEARER_TOKEN)
Anh: captures/<agent>/ — /files/
"""
from __future__ import annotations

import base64
import html
import json
import os
import re
import secrets
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


def _config_dir() -> Path:
    if getattr(sys, "frozen", False) and getattr(sys, "executable", None):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _load_env_file(path: Path) -> None:
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
        if key and key not in os.environ:
            os.environ[key] = val


_load_env_file(_config_dir() / "server.env")

_TOKEN_FILE = "auth.token"


def _token_file_path() -> Path:
    raw = (os.environ.get("AUTH_TOKEN_PATH") or "").strip()
    if raw:
        return Path(raw)
    return _config_dir() / _TOKEN_FILE


def _read_shared_token(path: Path) -> str | None:
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


def _resolve_bearer_token() -> str:
    env = (os.environ.get("BEARER_TOKEN") or "").strip()
    if env and env != "change-me":
        return env
    p = _token_file_path()
    existing = _read_shared_token(p)
    if existing:
        return existing
    t = secrets.token_hex(32)
    try:
        p.write_text(t + "\n", encoding="utf-8")
    except OSError:
        pass
    return t


def _default_db_path() -> Path:
    return _config_dir() / "monitor.db"


BEARER_TOKEN = _resolve_bearer_token()
ADMIN_TOKEN = (os.environ.get("ADMIN_TOKEN") or "").strip() or BEARER_TOKEN
DB_PATH = Path(os.environ.get("MONITOR_DB_PATH", _default_db_path()))
CAPTURES_ROOT = Path(os.environ.get("CAPTURES_DIR", str(_config_dir() / "captures")))


def _safe_agent_folder(agent_id: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", (agent_id or "").strip()).strip("_")
    return (s[:120] if s else None) or "unknown"


def _resolved_captures_subdir(folder_key: str) -> Path | None:
    """Thư mục con trong CAPTURES_ROOT; chặn path traversal. folder_key có thể có khoảng trắng → chuẩn hóa giống agent."""
    safe = _safe_agent_folder(unquote(folder_key))
    root = CAPTURES_ROOT.resolve()
    try:
        d = (CAPTURES_ROOT / safe).resolve()
    except OSError:
        return None
    try:
        d.relative_to(root)
    except ValueError:
        return None
    if not d.is_dir():
        return None
    return d


def _gallery_page_html(folder_display: str, d: Path) -> str:
    records = _list_jpeg_gallery_items(d)
    esc_folder = html.escape(folder_display)
    items: list[str] = []
    for rec in records:
        href = str(rec["url"])
        name = str(rec["name"])
        mt_label = str(rec.get("mtime_label") or "")
        items.append(
            "<li>"
            f'<a href="{html.escape(href, quote=True)}"><img src="{html.escape(href, quote=True)}" alt="" loading="lazy" /></a>'
            f'<div class="meta"><a href="{html.escape(href, quote=True)}">{html.escape(name)}</a>'
            f"<br><span>{html.escape(mt_label)}</span></div>"
            "</li>"
        )
    body = (
        "<ul class='grid'>" + "".join(items) + "</ul>"
        if items
        else "<p>Chưa có ảnh JPEG trong thư mục này.</p>"
    )
    return f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Ảnh — {esc_folder}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 16px; background: #fafafa; }}
h1 {{ font-size: 1.1rem; }}
a {{ color: #06c; }}
ul.grid {{ list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 16px; }}
ul.grid li {{ width: 220px; border: 1px solid #ddd; border-radius: 8px; padding: 8px; background: #fff; }}
ul.grid img {{ width: 100%; height: auto; max-height: 140px; object-fit: contain; display: block; }}
.meta {{ font-size: 12px; margin-top: 8px; word-break: break-all; }}
.meta span {{ color: #666; }}
nav {{ margin-bottom: 16px; }}
</style></head><body>
<nav><a href="/admin">← Admin</a></nav>
<h1>Danh sách ảnh: {esc_folder}</h1>
<p style="color:#666;font-size:14px">Mới nhất trước · {len(records)} file</p>
{body}
</body></html>"""


def _fmt_local_time(ts: float) -> str:
    try:
        from datetime import datetime

        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return ""


def _list_jpeg_gallery_items(d: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    try:
        for p in d.iterdir():
            if not p.is_file() or p.suffix.lower() != ".jpg":
                continue
            st = p.stat()
            qdir = quote(d.name, safe="")
            qf = quote(p.name, safe="")
            items.append(
                {
                    "name": p.name,
                    "url": f"/files/{qdir}/{qf}",
                    "mtime": st.st_mtime,
                    "mtime_label": _fmt_local_time(st.st_mtime),
                }
            )
    except OSError:
        pass
    items.sort(key=lambda x: float(x["mtime"]), reverse=True)
    return items


def _save_screen_jpeg(agent_id: str, ts: float, b64: str) -> tuple[dict[str, object], str | None]:
    """
    Ghi JPEG vao CAPTURES_ROOT/<agent>/screen_<ms>.jpg
    Tra ve (meta dict de gop vao screen_capture, loi hoac None).
    """
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception as e:
        return {}, f"base64: {e}"
    if not raw or raw[:2] != b"\xff\xd8":
        return {}, "khong phai JPEG hop le"
    folder = CAPTURES_ROOT / _safe_agent_folder(agent_id)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {}, str(e)
    ms = int(ts * 1000)
    fname = f"screen_{ms}.jpg"
    path = folder / fname
    if path.exists():
        fname = f"screen_{ms}_{secrets.token_hex(4)}.jpg"
        path = folder / fname
    try:
        path.write_bytes(raw)
    except OSError as e:
        return {}, str(e)
    rel = f"{_safe_agent_folder(agent_id)}/{fname}"
    meta: dict[str, object] = {
        "server_file": rel,
        "server_url_path": f"/files/{_safe_agent_folder(agent_id)}/{fname}",
        "server_bytes": len(raw),
    }
    return meta, None


def _admin_page_html() -> str:
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        p = Path(sys._MEIPASS) / "admin_ui.html"
    else:
        p = Path(__file__).resolve().parent / "admin_ui.html"
    try:
        if p.is_file():
            return p.read_text(encoding="utf-8")
    except OSError:
        pass
    return "<!DOCTYPE html><html><body><h1>Thieu admin_ui.html</h1></body></html>"


def _folder_screenshot_stats(folder_key: str) -> tuple[int, str | None]:
    d = CAPTURES_ROOT / folder_key
    if not d.is_dir():
        return 0, None
    try:
        jpgs = [f for f in d.iterdir() if f.suffix.lower() == ".jpg" and f.is_file()]
    except OSError:
        return 0, None
    if not jpgs:
        return 0, None
    latest = max(jpgs, key=lambda p: p.stat().st_mtime)
    return len(jpgs), f"/files/{folder_key}/{latest.name}"


def _agent_row_summary(agent_id: str, ts: float, blob: dict) -> dict:
    si = blob.get("system_info") if isinstance(blob.get("system_info"), dict) else {}
    fk = _safe_agent_folder(agent_id)
    n, latest_url = _folder_screenshot_stats(fk)
    ddr = blob.get("dns_recent_domains")
    dns_list: list[str] = []
    if isinstance(ddr, list):
        dns_list = [str(x) for x in ddr if x][:400]
    dns_note = blob.get("dns_recent_domains_note")
    if not isinstance(dns_note, str):
        dns_note = None
    nio = blob.get("network_io") if isinstance(blob.get("network_io"), dict) else None
    bf = blob.get("browser_foreground") if isinstance(blob.get("browser_foreground"), dict) else None
    dn_raw = blob.get("display_name")
    dn = dn_raw.strip() if isinstance(dn_raw, str) and dn_raw.strip() else None
    host = si.get("hostname")
    device_title = dn or host or agent_id
    return {
        "agent_id": agent_id,
        "folder_key": fk,
        "last_seen": ts,
        "display_name": dn,
        "hostname": host,
        "device_title": device_title,
        "os": si.get("os"),
        "cpu_percent": si.get("cpu_percent"),
        "memory_percent": si.get("memory_percent"),
        "memory_total": si.get("memory_total"),
        "memory_used": si.get("memory_used"),
        "cpu_count": si.get("cpu_count"),
        "os_version": si.get("os_version"),
        "disk_usage": si.get("disk_usage") if isinstance(si.get("disk_usage"), dict) else None,
        "screenshot_count": n,
        "latest_screen_url": latest_url,
        "dns_recent_domains": dns_list,
        "dns_recent_domains_note": dns_note,
        "network_bytes_sent": nio.get("bytes_sent") if nio else None,
        "network_bytes_recv": nio.get("bytes_recv") if nio else None,
        "network_io_interval_sec": nio.get("interval_seconds") if nio else None,
        "browser_foreground_interval_sec": bf.get("interval_seconds") if bf else None,
    }


class AgentData(BaseModel):
    agent_id: str
    timestamp: float
    display_name: str | None = None
    system_info: dict = Field(default_factory=dict)
    top_processes: list = Field(default_factory=list)
    network_connections: list = Field(default_factory=list)
    events: list | None = None
    process_allowlist: list | None = None
    enforcement_actions: list | None = None
    screen_jpeg_b64: str | None = None
    screen_capture: dict | None = None
    screen_capture_error: str | None = None
    dns_recent_domains: list | None = None
    dns_recent_domains_note: str | None = None
    network_io: dict | None = None
    browser_foreground: dict | None = None


app = FastAPI(
    title="Monitoring Control Server",
    description="Nhan du lieu dinh ky tu agent/bot giám sat (POST /api/agent/data), luu SQLite.",
    version="1.0.0",
)


@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS agent_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            data_json TEXT NOT NULL
        )"""
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_agent_time ON agent_data (agent_id, timestamp)")
        conn.commit()


@app.on_event("startup")
def _startup():
    init_db()
    try:
        CAPTURES_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def _check_auth(request: Request) -> None:
    auth = request.headers.get("Authorization") or ""
    expected = f"Bearer {BEARER_TOKEN}"
    if auth != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _check_admin(request: Request) -> None:
    auth = request.headers.get("Authorization") or ""
    expected = f"Bearer {ADMIN_TOKEN}"
    if auth != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    """Trinh duyet mac dinh hoi favicon — tra 204 de tranh 404 trong console."""
    return Response(status_code=204)


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    return HTMLResponse(_admin_page_html())


@app.get("/api/admin/agents")
async def admin_list_agents(request: Request):
    _check_admin(request)
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT agent_id, timestamp, data_json FROM agent_data
            WHERE id IN (SELECT MAX(id) FROM agent_data GROUP BY agent_id)
            ORDER BY timestamp DESC"""
        )
        rows = c.fetchall()
    agents: list[dict] = []
    for agent_id, ts, dj in rows:
        try:
            blob = json.loads(dj)
        except (json.JSONDecodeError, TypeError):
            continue
        agents.append(_agent_row_summary(agent_id, ts, blob))
    return {"agents": agents}


@app.get("/api/admin/gallery/{folder_key}")
async def admin_gallery_json(folder_key: str, request: Request):
    """JSON danh sach anh JPEG trong captures/<folder>/ (cho UI admin)."""
    _check_admin(request)
    d = _resolved_captures_subdir(folder_key)
    if d is None:
        raise HTTPException(status_code=404, detail="Không có thư mục ảnh")
    items = _list_jpeg_gallery_items(d)
    return {"folder_key": d.name, "count": len(items), "items": items}


@app.post("/api/agent/data")
async def receive_data(data: AgentData, request: Request):
    _check_auth(request)
    blob = data.model_dump()
    b64 = blob.pop("screen_jpeg_b64", None)
    if isinstance(b64, str) and b64.strip():
        meta, err = _save_screen_jpeg(data.agent_id, data.timestamp, b64.strip())
        sc = blob.get("screen_capture")
        if not isinstance(sc, dict):
            sc = {}
        sc.update(meta)
        blob["screen_capture"] = sc
        if err:
            blob["screen_server_save_error"] = err
    blob.pop("screen_jpeg_b64", None)
    payload = json.dumps(blob, ensure_ascii=False)
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO agent_data (agent_id, timestamp, data_json) VALUES (?, ?, ?)",
            (data.agent_id, data.timestamp, payload),
        )
        conn.commit()
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "service": "monitoring-control-ingest",
        "ingest": "/api/agent/data",
        "admin_ui": "/admin",
        "admin_api": "/api/admin/agents",
        "health": "/health",
        "docs": "/docs",
        "screens": "/files/",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/files/{folder_key}/", response_class=HTMLResponse, include_in_schema=False)
async def captures_folder_gallery(folder_key: str):
    """
    Liệt kê ảnh trong captures/<folder>/ (StaticFiles không có index thư mục → trước đây /files/.../ bị 404).
    folder_key có khoảng trắng được chuẩn hóa giống tên thư mục trên đĩa.
    """
    d = _resolved_captures_subdir(folder_key)
    if d is None:
        raise HTTPException(status_code=404, detail="Không có thư mục")
    return HTMLResponse(_gallery_page_html(d.name, d))


try:
    CAPTURES_ROOT.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
app.mount("/files", StaticFiles(directory=str(CAPTURES_ROOT)), name="captures")
