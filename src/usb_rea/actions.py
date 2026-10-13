"""Action markers: which transfers belong to which user action."""
from __future__ import annotations
import json
import time
from pathlib import Path

from .model import Action, Transfer


def load_markers(path: str | Path) -> list[dict]:
    """Markers file: JSON list of {label, start, end?} (epoch seconds).

    Missing `end` means "until the next marker starts" (or +infinity).
    """
    marks = json.loads(Path(path).read_text())
    marks = sorted(marks, key=lambda m: m["start"])
    for i, m in enumerate(marks):
        if m.get("end") is None:
            m["end"] = marks[i + 1]["start"] if i + 1 < len(marks) else float("inf")
    return marks


def append_marker(path: str | Path, label: str, ts: float | None = None) -> dict:
    p = Path(path)
    marks = json.loads(p.read_text()) if p.exists() else []
    now = time.time() if ts is None else ts
    if marks and marks[-1].get("end") is None:
        marks[-1]["end"] = now
    m = {"label": label, "start": now, "end": None}
    marks.append(m)
    p.write_text(json.dumps(marks, indent=1))
    return m


def assign(transfers: list[Transfer], marks: list[dict]) -> list[Action]:
    acts = [Action(m["label"], m["start"], m["end"]) for m in marks]
    for t in transfers:
        for a in acts:
            if a.start <= t.ts <= a.end:
                a.transfers.append(t)
                break
    return acts


def commands_of(action: Action) -> list[Transfer]:
    """Host->device messages that carry data (the interesting part)."""
    return [t for t in action.transfers if t.is_out and t.data]
