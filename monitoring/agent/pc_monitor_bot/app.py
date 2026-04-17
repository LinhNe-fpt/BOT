from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from . import __version__
from . import config
from .collector import build_payload
from .uplink import make_session, send_with_backoff

_FIRST_RUN_MARKER = "client_first_run.done"
_LOGON_TASK_MARKER = "register_logon_task.done"


def _maybe_register_logon_task_from_agent() -> None:
    """Dang ky Task Scheduler mot lan (pc-monitor-client.exe + Windows + REGISTER_LOGON_TASK)."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    if not config.REGISTER_LOGON_TASK:
        return
    root = config.app_dir()
    marker = root / _LOGON_TASK_MARKER
    if marker.exists():
        return
    try:
        from .win_autostart import register_pcmonitor_logon_task

        exe = str(Path(sys.executable).resolve())
        work = str(root.resolve())
        if register_pcmonitor_logon_task(exe, work):
            marker.write_text("1", encoding="utf-8")
    except Exception:
        pass


def _win_msg(title: str, body: str, *, warning: bool = False) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        flag = 0x30 if warning else 0x40
        ctypes.windll.user32.MessageBoxW(0, body, title, flag)
    except Exception:
        pass


def _silent_write_last_error(msg: str) -> None:
    try:
        p = config.app_dir() / "client_last_error.txt"
        p.write_text(msg[:4000], encoding="utf-8")
    except OSError:
        pass


def _maybe_client_first_run_notice() -> None:
    """Lan chay dau tren may client: hop thoai token + agent (Windows)."""
    if not config.SILENT_CLIENT or sys.platform != "win32":
        return
    root = config.app_dir()
    marker = root / _FIRST_RUN_MARKER
    if marker.exists():
        return
    tok = config.SECRET_TOKEN
    if not tok or tok == "change-me":
        tok_show = (
            "Thiếu token.\n\nĐặt SECRET_TOKEN trong agent.env hoặc copy file auth.token "
            "cạnh pc-monitor-client.exe rồi chạy lại."
        )
        _win_msg("PC Monitor", tok_show, warning=True)
        return
    dn_line = (
        f"Tên hiển thị: {config.DEVICE_DISPLAY_NAME}\n"
        if config.DEVICE_DISPLAY_NAME
        else ""
    )
    body = (
        f"Chương trình chạy TRÊN MÁY NÀY để chụp màn hình và GỬI VỀ MÁY CHỦ.\n"
        f"(Máy chủ không tự lấy ảnh từ xa — bắt buộc có agent trên máy được giám sát.)\n\n"
        f"Máy này (Agent ID): {config.AGENT_ID}\n"
        f"{dn_line}"
        f"Token: {tok}\n\n"
        f"Gửi về: {config.API_URL}\n\n"
        f"OK — chạy nền. Xoá client_first_run.done nếu muốn xem lại hộp thoại."
    )
    _win_msg("PC Monitor — đã cài", body, warning=False)
    try:
        marker.write_text("1", encoding="utf-8")
    except OSError:
        pass


def _exit_if_second_silent_instance() -> None:
    """Windows + SILENT_CLIENT: thoát im lặng nếu đã có một tiến trình client nền."""
    if sys.platform != "win32" or not config.SILENT_CLIENT:
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetLastError(0)
        h = kernel32.CreateMutexW(None, True, "Local\\PCMonitorClientSilent_v1")
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            if h:
                kernel32.CloseHandle(h)
            sys.exit(0)
    except Exception:
        pass


def validate_config() -> None:
    if not config.SILENT_CLIENT and (not config.SECRET_TOKEN or config.SECRET_TOKEN == "change-me"):
        print("Cảnh báo: SECRET_TOKEN chưa được đặt an toàn.", file=sys.stderr)
    config.validate_api_url()


def run_command_listener() -> None:
    if not config.COMMAND_SECRET:
        print("COMMAND_LISTENER bật nhưng thiếu COMMAND_SECRET — bỏ qua.", file=sys.stderr)
        return
    try:
        import command_listener
    except ImportError:
        print("Thiếu command_listener.py — tắt COMMAND_LISTENER.", file=sys.stderr)
        return
    command_listener.main(
        host="127.0.0.1",
        port=config.COMMAND_LISTENER_PORT,
        secret=config.COMMAND_SECRET,
    )


def _print_startup_banner() -> None:
    screen_note = (
        "luu screenshots/ (SCREEN_SAVE_LOCAL=1)"
        if config.SCREEN_SAVE_LOCAL
        else "khong luu dia — chi gui anh len server"
    )
    print(
        f"[PC Monitor Bot v{__version__}] Thu thap: he thong, tien trinh, mang, USB; "
        f"chup man hinh moi {config.INTERVAL_SECONDS}s; {screen_note} (dev: python gui_launcher.py).",
        file=sys.stderr,
    )
    if getattr(sys, "frozen", False):
        print(
            f"[PC Monitor Bot] agent_id={config.AGENT_ID} | outbox={config.CACHE_DIR}",
            file=sys.stderr,
        )


def _run_loop(*, silent: bool) -> None:
    session = make_session()
    if config.COMMAND_LISTENER and not silent:
        t = threading.Thread(target=run_command_listener, daemon=True)
        t.start()
    elif config.COMMAND_LISTENER and silent:
        pass
    if not silent:
        _print_startup_banner()
        view_hint = "xem screenshots/ & " if config.SCREEN_SAVE_LOCAL else "anh tren server /files/ — "
        print(
            f"PC Monitor Bot — máy «{config.AGENT_ID}» → {config.API_URL} "
            f"(lap lai moi ~{config.INTERVAL_SECONDS}s: chup + gui; {view_hint}log stderr)"
        )
    cycle = 0
    while True:
        cycle += 1
        t0 = time.monotonic()
        try:
            payload = build_payload(cycle=cycle)
            send_with_backoff(session, payload)
        except Exception as e:
            if silent:
                _silent_write_last_error(f"{type(e).__name__}: {e}")
            else:
                print(f"Lỗi thu thập/gửi: {e}", file=sys.stderr)
        elapsed = time.monotonic() - t0
        wait = max(0.0, float(config.INTERVAL_SECONDS) - elapsed)
        if wait > 0:
            time.sleep(wait)


def main() -> None:
    validate_config()
    _run_loop(silent=False)


def main_silent() -> None:
    """Chế độ máy ngoài: không console, mở hộp thoại token lần đầu (Windows)."""
    _exit_if_second_silent_instance()
    validate_config()
    _maybe_register_logon_task_from_agent()
    _maybe_client_first_run_notice()
    _run_loop(silent=True)
