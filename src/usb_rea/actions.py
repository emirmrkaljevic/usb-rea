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


def find_background(transfers: list[Transfer], min_count: int = 4) -> list[dict]:
    """Host->device messages the vendor app sends on its own (status polls, keep-alives).

    A payload counts as background when the identical message (same channel, same bytes) is sent
    at least `min_count` times, at a steady rhythm, and mostly on its own: at least half of the
    copies have no other host->device message close by. That keeps a constant "apply" packet,
    which always follows a real command, out of this list.
    Returns one dict per payload: key, data, count, period (s), frames.
    """
    outs = sorted((t for t in transfers if t.is_out and t.data), key=lambda t: t.ts)
    groups: dict[tuple, list[Transfer]] = {}
    for t in outs:
        groups.setdefault((t.key(), t.data), []).append(t)
    found = []
    for (key, data), ts in groups.items():
        if len(ts) < min_count:
            continue
        iv = sorted(b.ts - a.ts for a, b in zip(ts, ts[1:]))
        period = iv[len(iv) // 2]
        if period <= 0:
            continue
        # steady rhythm: most intervals within 35% of the median (a missed or late poll is fine)
        if sum(abs(x - period) <= 0.35 * period for x in iv) < 0.6 * len(iv):
            continue
        window = 0.1 * period
        others = [t.ts for t in outs if (t.key(), t.data) != (key, data)]
        alone = sum(not any(abs(o - t.ts) <= window for o in others) for t in ts)
        if alone < 0.5 * len(ts):
            continue
        found.append({"key": key, "data": data, "count": len(ts), "period": round(period, 3),
                      "frames": [t.frame for t in ts]})
    return found


def drop_background(transfers: list[Transfer], background: list[dict]) -> list[Transfer]:
    bg = {(b["key"], b["data"]) for b in background}
    return [t for t in transfers if not (t.is_out and t.data and (t.key(), t.data) in bg)]


def segment_by_gaps(transfers: list[Transfer], labels: list[str]) -> list[dict]:
    """Build markers without timestamps: split host->device traffic at the largest pauses.

    For captures made in Wireshark/USBPcap where you simply clicked the actions in order with a
    short pause between them. Returns markers usable by `assign`.
    """
    outs = sorted((t for t in transfers if t.is_out and t.data), key=lambda t: t.ts)
    n = len(labels)
    if n == 0 or len(outs) < n:
        raise ValueError(f"{len(labels)} labels but only {len(outs)} host->device messages in the capture")
    gaps = sorted(range(1, len(outs)), key=lambda i: outs[i].ts - outs[i - 1].ts, reverse=True)[:n - 1]
    cuts = [0] + sorted(gaps) + [len(outs)]
    marks = []
    for label, a, b in zip(labels, cuts, cuts[1:]):
        marks.append({"label": label, "start": outs[a].ts - 1e-6, "end": outs[b - 1].ts + 1e-6})
    return marks


def read_labels(spec: str) -> list[str]:
    """Labels from a file (one per line) or a ';'-separated string."""
    p = Path(spec)
    if p.is_file():
        return [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")]
    return [s.strip() for s in spec.split(";") if s.strip()]
