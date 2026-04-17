"""Windows: dang ky Task Scheduler chay pc-monitor-client khi dang nhap (mot lan)."""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path


def register_pcmonitor_logon_task(exe_path: str, work_dir: str) -> bool:
    """
    Task ten PCMonitorClient — giong pc_monitor_client_common.ps1.
    Can quyen nguoi dung hien tai (khong can Admin cho AtLogOn nhieu may).
    """
    if sys.platform != "win32":
        return False
    exe_json = json.dumps(exe_path, ensure_ascii=True)
    work_json = json.dumps(work_dir, ensure_ascii=True)
    ps = f"""
$ErrorActionPreference = 'Stop'
$taskName = 'PCMonitorClient'
$exePath = {exe_json}
$workDir = {work_json}
$fullUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
try {{ Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue }} catch {{ }}
$action = New-ScheduledTaskAction -Execute $exePath -WorkingDirectory $workDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $fullUser
$principal = New-ScheduledTaskPrincipal -UserId $fullUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName `
    -Description 'PC Monitor client - chay nen khi dang nhap' `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
"""
    enc = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(
            [
                str(Path(sys.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                enc,
            ],
            capture_output=True,
            timeout=90,
            creationflags=flags,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0
