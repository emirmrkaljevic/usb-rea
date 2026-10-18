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


def _periodic(ts: list[Transfer], outs: list[Transfer]) -> float | None:
    """Median period if `ts` is sent at a steady rhythm and mostly on its own, else None."""
    iv = sorted(b.ts - a.ts for a, b in zip(ts, ts[1:]))
    period = iv[len(iv) // 2]
    if period <= 0:
        return None
    # steady rhythm: most intervals within 35% of the median (a missed or late poll is fine)
    if sum(abs(x - period) <= 0.35 * period for x in iv) < 0.6 * len(iv):
        return None
    window = 0.1 * period
    mine = {id(t) for t in ts}
    others = [t.ts for t in outs if id(t) not in mine]
    alone = sum(not any(abs(o - t.ts) <= window for o in others) for t in ts)
    return period if alone >= 0.5 * len(ts) else None


def _counter_candidates(outs: list[Transfer], skip: set, min_count: int) -> list[tuple]:
    """Groups of same-shape messages that differ only in a +1 sequence byte (and maybe a trailing
    checksum byte that changes with it). Returns (key, template, masked positions, transfers)."""
    shapes: dict[tuple, list[Transfer]] = {}
    for t in outs:
        if id(t) not in skip and len(t.data) <= 64:
            shapes.setdefault((t.key(), len(t.data)), []).append(t)
    cands = []
    for (key, n), ts in shapes.items():
        if len(ts) < min_count:
            continue
        for j in range(n):
            for mask in ({j}, {j, n - 1}) if j != n - 1 else ({j},):
                groups: dict[bytes, list[Transfer]] = {}
                for t in ts:
                    groups.setdefault(bytes(0 if i in mask else b for i, b in enumerate(t.data)), []).append(t)
                for tpl, g in groups.items():
                    if len(g) < min_count:
                        continue
                    steps = [(b.data[j] - a.data[j]) % 256 for a, b in zip(g, g[1:])]
                    if sum(x == 1 for x in steps) >= 0.8 * len(steps):
                        cands.append((key, tpl, tuple(sorted(mask)), g))
    # prefer the biggest groups, then the fewest masked bytes
    cands.sort(key=lambda c: (-len(c[3]), len(c[2])))
    return cands


def find_background(transfers: list[Transfer], min_count: int = 4) -> list[dict]:
    """Host->device messages the vendor app sends on its own (status polls, keep-alives).

    A payload counts as background when the identical message (same channel, same bytes) is sent
    at least `min_count` times, at a steady rhythm, and mostly on its own: at least half of the
    copies have no other host->device message close by. That keeps a constant "apply" packet,
    which always follows a real command, out of this list.
    Polls that carry a sequence number are found too: same-shape messages that differ only in a
    byte counting up by one (plus, optionally, a trailing checksum byte). Because a user could step
    a value by one at a steady pace, these need at least 2 * min_count (and 8) copies.
    Returns one dict per payload: key, data, mask (positions that vary), count, period (s), frames.
    """
    outs = sorted((t for t in transfers if t.is_out and t.data), key=lambda t: t.ts)
    groups: dict[tuple, list[Transfer]] = {}
    for t in outs:
        groups.setdefault((t.key(), t.data), []).append(t)
    found, claimed = [], set()
    for (key, data), ts in groups.items():
        if len(ts) < min_count:
            continue
        period = _periodic(ts, outs)
        if period is None:
            continue
        claimed |= {id(t) for t in ts}
        found.append({"key": key, "data": data, "mask": [], "count": len(ts), "period": round(period, 3),
                      "frames": [t.frame for t in ts], "ids": {id(t) for t in ts}})
    for key, tpl, mask, ts in _counter_candidates(outs, claimed, max(2 * min_count, 8)):
        if any(id(t) in claimed for t in ts):
            continue
        period = _periodic(ts, outs)
        if period is None:
            continue
        claimed |= {id(t) for t in ts}
        found.append({"key": key, "data": tpl, "mask": list(mask), "count": len(ts),
                      "period": round(period, 3), "frames": [t.frame for t in ts],
                      "ids": {id(t) for t in ts}})
    return found


def drop_background(transfers: list[Transfer], background: list[dict]) -> list[Transfer]:
    ids = set().union(*(b["ids"] for b in background)) if background else set()
    return [t for t in transfers if id(t) not in ids]


def pattern(data: bytes, mask) -> str:
    """Hex payload with the varying (sequence/checksum) bytes shown as ??."""
    return " ".join("??" if i in mask else f"{b:02x}" for i, b in enumerate(data))


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
