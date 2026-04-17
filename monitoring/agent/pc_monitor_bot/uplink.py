from __future__ import annotations

import json
import random
import sys
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config


def _log_send(msg: str) -> None:
    if config.SILENT_CLIENT:
        try:
            (config.app_dir() / "client_last_error.txt").write_text(msg[:4000], encoding="utf-8")
        except OSError:
            pass
        return
    print(msg, file=sys.stderr)


def make_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=config.MAX_RETRIES,
        connect=config.MAX_RETRIES,
        read=config.MAX_RETRIES,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["POST"]),
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s


def _queue_path():
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return config.CACHE_DIR / "queue.jsonl"


def enqueue_failed(payload: dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=False)
    p = _queue_path()
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _read_queue_max(max_lines: int = 500) -> list[str]:
    p = _queue_path()
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    return lines[-max_lines:]


def _rewrite_queue(remaining: list[str]) -> None:
    p = _queue_path()
    if not remaining:
        if p.exists():
            p.unlink()
        return
    p.write_text("\n".join(remaining) + "\n", encoding="utf-8")


def send_payload(session: requests.Session, payload: dict[str, Any]) -> bool:
    config.reload_secret_if_file()
    headers = {
        "Authorization": f"Bearer {config.SECRET_TOKEN}",
        "Content-Type": "application/json",
    }
    r = session.post(config.API_URL, json=payload, headers=headers, timeout=config.REQUEST_TIMEOUT)
    if r.status_code == 200:
        return True
    _log_send(f"Lỗi gửi: HTTP {r.status_code} {r.text[:200]}")
    if r.status_code == 401 and not config.SILENT_CLIENT:
        print(
            "  → 401: token không khớp HOẶC đang gọi nhầm server (port khác / instance cũ trên :8000). "
            "Cùng thư mục: auth.token chung; server .exe mặc định :8010, API_URL bot phải trùng PORT.",
            file=sys.stderr,
        )
    return False


def flush_queue(session: requests.Session) -> None:
    lines = _read_queue_max()
    if not lines:
        return
    kept: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if send_payload(session, payload):
            continue
        kept.append(line)
    _rewrite_queue(kept)


def send_with_backoff(session: requests.Session, payload: dict[str, Any]) -> None:
    flush_queue(session)
    attempt = 0
    while True:
        try:
            if send_payload(session, payload):
                flush_queue(session)
                return
        except requests.RequestException as e:
            _log_send(f"Không kết nối được server: {e}")
        attempt += 1
        wait = min(120.0, (config.RETRY_BACKOFF_BASE**attempt) + random.uniform(0, 1))
        if not config.SILENT_CLIENT:
            print(f"Retry sau {wait:.1f}s (lần {attempt})...", file=sys.stderr)
        time.sleep(wait)
        if attempt >= config.MAX_RETRIES:
            enqueue_failed(payload)
            _log_send("Đã lưu payload vào outbox, thử lại ở chu kỳ sau.")
            return
