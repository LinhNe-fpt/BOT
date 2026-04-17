from __future__ import annotations

import base64
import io
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config

SCREEN_LAST_NAME = "screen_last.jpg"


def _local_hist_dir() -> Path | None:
    """Thu muc luu JPEG moi chu ky tren dia; None = khong ghi file (chi gui server)."""
    raw = getattr(config, "SCREEN_SAVE_DIR", "") or ""
    if isinstance(raw, str) and raw.strip():
        return Path(raw.strip()).expanduser().resolve()
    if config.SCREEN_SAVE_LOCAL:
        return (config.app_dir() / "screenshots").resolve()
    return None


def _prune_screenshots(hist_dir: Path, keep: int) -> None:
    if keep <= 0:
        return
    try:
        files = sorted(hist_dir.glob("screen_*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    for p in files[keep:]:
        try:
            p.unlink()
        except OSError:
            pass


def capture_screen_jpeg_b64(cycle: int | None = None) -> dict[str, Any]:
    """
    Gui JPEG len server (base64) moi chu ky.
    Luu dia neu dat SCREEN_SAVE_DIR (uu tien) hoac SCREEN_SAVE_LOCAL=1 (thu muc screenshots/ canh .exe).
    SCREEN_KEEP_MAX / SCREEN_WRITE_LAST_FILE ap dung cho thu muc luu da chon.
    """
    if not config.SCREEN_CAPTURE:
        return {}
    try:
        from PIL import Image, ImageGrab
    except ImportError:
        return {"screen_capture_error": "Pillow chua cai (pip install Pillow)"}

    out: dict[str, Any] = {}
    im = None
    try:
        im = ImageGrab.grab(all_screens=True)
    except Exception as e:
        return {"screen_capture_error": str(e)}

    try:
        w, h = im.size
        mw = max(320, min(config.SCREEN_MAX_WIDTH, 3840))
        if w > mw:
            ratio = mw / float(w)
            nh = max(1, int(h * ratio))
            im = im.resize((mw, nh), Image.Resampling.LANCZOS)
            w, h = im.size

        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")

        buf = io.BytesIO()
        # subsampling 0 = 4:4:4, chu/net ro hon; file lon hon. Chat luong thap dung 4:2:0.
        sub = 0 if config.SCREEN_JPEG_QUALITY >= 68 else 2
        im.save(
            buf,
            format="JPEG",
            quality=config.SCREEN_JPEG_QUALITY,
            optimize=True,
            subsampling=sub,
        )
        raw = buf.getvalue()

        hist_name: str | None = None
        last_warn: str | None = None
        hist_dir = _local_hist_dir()
        if hist_dir is not None:
            try:
                hist_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                return {"screen_capture_error": f"tao thu muc luu anh: {e}"}
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            hist_name = f"screen_{ts}_{int(time.time() * 1000) % 100000}.jpg"
            hist_path = hist_dir / hist_name
            try:
                hist_path.write_bytes(raw)
                _prune_screenshots(hist_dir, config.SCREEN_KEEP_MAX)
            except OSError as e:
                return {"screen_capture_error": f"ghi anh dia phuong: {e}"}

            if config.SCREEN_WRITE_LAST_FILE:
                try:
                    (hist_dir / SCREEN_LAST_NAME).write_bytes(raw)
                except OSError as e:
                    last_warn = str(e)

        b64 = base64.b64encode(raw).decode("ascii")
        max_b64 = config.SCREEN_MAX_B64_CHARS
        if len(b64) > max_b64:
            return {
                "screen_capture_error": (
                    f"anh qua lon sau nen ({len(b64)} > {max_b64}), tang SCREEN_MAX_WIDTH hoac giam chat luong"
                )
            }

        out["screen_jpeg_b64"] = b64
        sc: dict[str, Any] = {
            "width": w,
            "height": h,
            "format": "jpeg",
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "cycle": cycle,
            "local_save": hist_dir is not None,
        }
        if hist_name and hist_dir is not None:
            sc["file"] = hist_name
            sc["folder"] = str(hist_dir)
        if hist_dir is not None and config.SCREEN_WRITE_LAST_FILE:
            sc["latest_copy"] = str(hist_dir / SCREEN_LAST_NAME)
        if last_warn:
            sc["last_file_error"] = last_warn
        out["screen_capture"] = sc
        if not config.SILENT_CLIENT:
            tag = f"chu ky #{cycle}" if cycle is not None else "chup"
            if hist_dir is not None and hist_name:
                msg = f"[PC Monitor Bot] {tag}: da chup -> {hist_path}"
                if config.SCREEN_WRITE_LAST_FILE:
                    msg += f" (+ {SCREEN_LAST_NAME})"
                print(msg, file=sys.stderr)
            else:
                print(f"[PC Monitor Bot] {tag}: da chup, chi gui server (khong luu dia)", file=sys.stderr)
    finally:
        if im is not None:
            try:
                im.close()
            except Exception:
                pass

    return out
