"""Capture helpers: thin wrappers around dumpcap/tshark (Linux usbmon) and USBPcapCMD (Windows)."""
from __future__ import annotations
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

PIDFILE = ".usb-rea-capture.pid"


def capture_command(out: str, bus: int = 0) -> list[str]:
    if sys.platform.startswith("win"):
        exe = shutil.which("USBPcapCMD.exe") or r"C:\Program Files\USBPcap\USBPcapCMD.exe"
        return [exe, "-d", rf"\\.\USBPcap{bus or 1}", "-o", out, "-A"]
    tool = shutil.which("dumpcap") or shutil.which("tshark")
    if not tool:
        raise RuntimeError("need dumpcap or tshark (apt install tshark) and `sudo modprobe usbmon`")
    return [tool, "-i", f"usbmon{bus}", "-w", out, "-q"]


def start(out: str, bus: int = 0, workdir: str = ".") -> int:
    proc = subprocess.Popen(capture_command(out, bus), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    Path(workdir, PIDFILE).write_text(str(proc.pid))
    return proc.pid


def stop(workdir: str = ".") -> bool:
    p = Path(workdir, PIDFILE)
    if not p.exists():
        return False
    try:
        os.kill(int(p.read_text()), signal.SIGINT)
    except ProcessLookupError:
        pass
    p.unlink()
    return True
