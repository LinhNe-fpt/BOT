from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Tk sau khi da nap config (agent.env)
def run_gui() -> None:
    import socket
    import tkinter as tk
    from tkinter import messagebox, ttk

    from pc_monitor_bot import config

    hostname = socket.gethostname()
    agent_id = config.AGENT_ID

    root = tk.Tk()
    root.title("PC Monitor Bot — Thông tin máy")
    root.minsize(440, 300)
    root.geometry("520x340")

    frm = ttk.Frame(root, padding=14)
    frm.pack(fill=tk.BOTH, expand=True)

    ttk.Label(
        frm,
        text="Máy đã cài bot — dùng tên dưới đây để nhận diện trên server",
        wraplength=480,
    ).pack(anchor=tk.W)

    ttk.Label(frm, text="Tên máy (hostname Windows/Linux):", font=("Segoe UI", 9, "bold")).pack(
        anchor=tk.W, pady=(14, 2)
    )
    v_host = tk.StringVar(value=hostname)
    ttk.Entry(frm, textvariable=v_host, width=56, state="readonly").pack(anchor=tk.W, fill=tk.X)

    ttk.Label(frm, text="Agent ID (gửi kèm mỗi lần lên server):", font=("Segoe UI", 9, "bold")).pack(
        anchor=tk.W, pady=(12, 2)
    )
    v_agent = tk.StringVar(value=agent_id)
    ttk.Entry(frm, textvariable=v_agent, width=56, state="readonly").pack(anchor=tk.W, fill=tk.X)

    status = tk.StringVar(
        value="Chạy client: deploy\\dist\\pc-monitor-client.exe hoặc nút bên dưới (dev: bot.py)."
    )

    def clip(text: str, label: str) -> None:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        status.set(f"Da sao chep {label} vao bo nho.")

    row = ttk.Frame(frm)
    row.pack(fill=tk.X, pady=10)
    ttk.Button(row, text="Sao chép tên máy", command=lambda: clip(hostname, "ten may")).pack(
        side=tk.LEFT, padx=(0, 6)
    )
    ttk.Button(row, text="Sao chép Agent ID", command=lambda: clip(agent_id, "Agent ID")).pack(side=tk.LEFT)

    ttk.Label(frm, textvariable=status, foreground="#555", wraplength=480).pack(anchor=tk.W, pady=(8, 0))

    proc_box: dict = {"p": None}

    def start_bot() -> None:
        if proc_box["p"] is not None and proc_box["p"].poll() is None:
            messagebox.showinfo("PC Monitor Bot", "Một tiến trình đã được mở trước đó.")
            return
        agent_dir = Path(__file__).resolve().parent.parent
        dist_client = agent_dir.parent / "deploy" / "dist" / "pc-monitor-client.exe"
        here = Path(sys.executable).resolve().parent
        local_client = here / "pc-monitor-client.exe"
        flags_console = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        try:
            if local_client.is_file():
                proc_box["p"] = subprocess.Popen([str(local_client)], cwd=str(here))
                status.set("Đã chạy pc-monitor-client.exe (cùng thư mục với Python).")
            elif dist_client.is_file():
                proc_box["p"] = subprocess.Popen([str(dist_client)], cwd=str(dist_client.parent))
                status.set("Đã chạy pc-monitor-client.exe từ deploy\\dist.")
            else:
                proc_box["p"] = subprocess.Popen(
                    [sys.executable, str(agent_dir / "bot.py")],
                    creationflags=flags_console,
                    cwd=str(agent_dir),
                )
                status.set("Đã mở console chạy bot.py (môi trường dev).")
        except OSError as e:
            messagebox.showerror("Lỗi", str(e))

    ttk.Button(frm, text="Chạy giám sát (client .exe hoặc bot.py)", command=start_bot).pack(
        anchor=tk.W, pady=(16, 0)
    )

    api_short = config.API_URL if len(config.API_URL) < 70 else config.API_URL[:67] + "..."
    ttk.Label(frm, text=f"API: {api_short}", font=("Consolas", 8), foreground="#666").pack(
        anchor=tk.W, pady=(14, 0)
    )

    screen_hint = (
        "Ảnh: lưu screenshots/ (bật SCREEN_SAVE_LOCAL=1)."
        if config.SCREEN_SAVE_LOCAL
        else "Ảnh: mặc định chỉ gửi server — không lưu trên máy này (SCREEN_SAVE_LOCAL=1 để lưu cục bộ)."
    )
    ttk.Label(
        frm,
        text=screen_hint,
        font=("Segoe UI", 8),
        foreground="#666",
        wraplength=480,
    ).pack(anchor=tk.W, pady=(8, 0))

    root.mainloop()
