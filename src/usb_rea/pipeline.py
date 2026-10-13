"""One-call analysis used by both the CLI and the MCP server."""
from __future__ import annotations
import hashlib
from pathlib import Path

from .actions import assign, load_markers
from .infer import infer, Protocol
from .pcap import find_ids, read_transfers


def default_markers(capture: str | Path) -> Path:
    return Path(str(capture) + ".actions.json")


def analyze(capture: str | Path, markers: str | Path | None = None, device: int | None = None) -> Protocol:
    ts = read_transfers(capture)
    ids = find_ids(ts)
    if device is None:
        # the device with the most host->device data is almost always the target
        counts: dict[int, int] = {}
        for t in ts:
            if t.is_out and t.data and t.device != 0:
                counts[t.device] = counts.get(t.device, 0) + 1
        device = max(counts, key=counts.get) if counts else None
    ts = [t for t in ts if device is None or t.device == device]
    vid, pid = ids.get(device, (None, None))
    acts = assign(ts, load_markers(markers or default_markers(capture)))
    return infer(acts, vid, pid)


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
