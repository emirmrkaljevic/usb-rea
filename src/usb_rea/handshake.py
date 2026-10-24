"""Handshake: what the vendor app sends once when it opens the device, before the first action.

A handshake step is a host->device message (or a class/vendor control read) that is captured before
the first action marker, is not a background poll, and is never sent again later in the capture
(identical channel and bytes). Each step is paired with the IN data that answers it: the completion
of a control read, or the first bulk/interrupt IN transfer before the next host->device message.

With one copy of each message there is nothing to diff, so the claims are deliberately narrow:
- a checksum is claimed only when one algorithm fits the trailing bytes of every request (or every
  reply) of the handshake, with at least two messages, or a 16-bit one fits a single message;
- a session token is a run of 3+ reply bytes (not all one value, not checksum bytes, not a copy of
  the step's own request) that shows up again in a later handshake request or, at the same offset,
  in every captured copy of a command;
- an echo is a run of 3+ request bytes that the reply repeats (a host challenge sent back).
Every other reply byte is expected to come back unchanged when a driver replays the handshake.
"""
from __future__ import annotations
from bisect import bisect_right

from .checksums import CHECKSUMS, compute
from .model import Transfer, is_observation
from .responses import MAX_REPLY, WINDOW, is_control_read

MIN_RUN = 3
MAX_STEPS = 32


def _checksum(msgs: list[bytes]) -> dict | None:
    """One algorithm over bytes [start:n-w] stored in the last w bytes of every message."""
    msgs = [m for m in msgs if m]
    if not msgs:
        return None
    for algo, (w, _) in CHECKSUMS.items():
        if len(msgs) < 2 and w < 2:
            continue
        for endian in (("le", "be") if w == 2 else ("le",)):
            for start in (0, 1):
                if all(len(m) >= start + w + 2 and int.from_bytes(m[-w:], "little" if endian == "le" else "big")
                       == compute(algo, m[start:len(m) - w]) for m in msgs):
                    return {"algo": algo, "width": w, "endian": endian, "start": start}
    return None


def _ck_span(ck: dict | None, n: int) -> set[int]:
    return set(range(n - ck["width"], n)) if ck else set()


def _runs(a: bytes, b: bytes, skip_a: set[int], skip_b: set[int]) -> list[tuple[int, int, int]]:
    """Maximal common runs (offset in a, offset in b, length) of MIN_RUN+ bytes, not all one value."""
    out = []
    for i in range(len(a)):
        for j in range(len(b)):
            if i and j and a[i - 1] == b[j - 1] and i - 1 not in skip_a and j - 1 not in skip_b:
                continue  # not maximal: the run started earlier
            n = 0
            while i + n < len(a) and j + n < len(b) and a[i + n] == b[j + n] \
                    and i + n not in skip_a and j + n not in skip_b:
                n += 1
            if n >= MIN_RUN and len(set(a[i:i + n])) > 1:
                out.append((i, j, n))
    return out


def _reply(q: Transfer, ordered: list[Transfer], frames: list[int]) -> Transfer | None:
    for t in ordered[bisect_right(frames, q.frame):]:
        if t.ts - q.ts > WINDOW:
            return None
        if is_control_read(q):
            if t.xfer_type == 2 and t.is_in and t.data and t.setup is None:
                return t
            continue
        if t.is_out and t.data:
            return None  # the next message went out first: this one got no reply
        if t.is_in and t.data and t.xfer_type != 2:
            return t if len(t.data) <= MAX_REPLY else None
    return None


def find_handshake(transfers: list[Transfer], background: list[dict], marks: list[dict],
                   commands: list = (), t0: float = 0.0) -> list[dict]:
    """Handshake steps (dicts, JSON-ready) found before the first action marker."""
    starts = [m["start"] for m in marks if not is_observation(m["label"])]
    if not starts:
        return []
    first = min(starts)
    polls = set().union(*(b["ids"] for b in background)) if background else set()
    ordered = sorted(transfers, key=lambda t: t.frame)
    frames = [t.frame for t in ordered]

    def query(t):
        return (t.is_out and t.data) or is_control_read(t)

    later = {(t.key(), t.data) for t in ordered if t.ts >= first and query(t)}
    qs = [t for t in ordered if t.ts < first and query(t) and id(t) not in polls
          and (t.key(), t.data) not in later][:MAX_STEPS]
    steps = []
    for i, q in enumerate(qs, 1):
        r = _reply(q, ordered, frames)
        steps.append({
            "step": i, "frame": q.frame, "time": round(q.ts - t0, 3),
            "endpoint": q.endpoint, "xfer_type": q.xfer_type, "setup": q.setup.hex() if q.setup else None,
            "read": is_control_read(q), "request": q.data.hex(" "),
            "reply": r.data.hex(" ") if r else None, "reply_frame": r.frame if r else None,
            "reply_endpoint": r.endpoint if r else None, "reply_xfer_type": r.xfer_type if r else None,
            "latency_ms": round((r.ts - q.ts) * 1000, 1) if r else None,
            "request_checksum": None, "reply_checksum": None, "uses": [], "tokens": [], "echoes": [],
            "expect": None,
        })
    if not steps:
        return []
    reqs = [bytes.fromhex(s["request"]) for s in steps]
    reps = [bytes.fromhex(s["reply"]) if s["reply"] else b"" for s in steps]
    qck, rck = _checksum([m for m, s in zip(reqs, steps) if not s["read"]]), _checksum(reps)
    for s, m, r in zip(steps, reqs, reps):
        if qck and m and not s["read"]:
            s["request_checksum"] = {**qck, "covers": [qck["start"], len(m) - qck["width"]]}
        if rck and r:
            s["reply_checksum"] = {**rck, "covers": [rck["start"], len(r) - rck["width"]]}

    def skip_q(k):
        return _ck_span(steps[k]["request_checksum"], len(reqs[k]))

    def skip_r(k):
        return _ck_span(steps[k]["reply_checksum"], len(reps[k]))

    taken: list[set[int]] = [set() for _ in steps]   # reply bytes claimed as tokens
    for i, s in enumerate(steps):
        if not reps[i]:
            continue
        own = {a for a, _, n in _runs(reps[i], reqs[i], skip_r(i), skip_q(i)) for a in range(a, a + n)}
        for a, b, n in _runs(reps[i], reqs[i], skip_r(i), skip_q(i)):
            s["echoes"].append({"offset": a, "width": n, "query_offset": b})
        tokens: dict[tuple, dict] = {}

        def use(a, n, where):
            tok = tokens.setdefault((a, n), {"reply_offset": a, "width": n, "used_by": []})
            tok["used_by"].append(where)
            taken[i].update(range(a, a + n))
        for j in range(i + 1, len(steps)):
            for a, b, n in _runs(reps[i], reqs[j], skip_r(i) | own, skip_q(j)):
                if any(range(b, b + n) == range(u["offset"], u["offset"] + u["width"]) for u in steps[j]["uses"]):
                    continue  # an earlier reply already explains these bytes
                use(a, n, {"step": j + 1, "offset": b})
                steps[j]["uses"].append({"step": i + 1, "reply_offset": a, "offset": b, "width": n})
        for c in commands:
            for k, packet in enumerate([c, *c.steps]):
                datas = [bytes.fromhex(hx.replace(" ", "")) for _, hx, _ in packet.samples]
                if not datas:
                    continue
                for a, b, n in _runs(reps[i], datas[0], skip_r(i) | own, set()):
                    if all(d[b:b + n] == reps[i][a:a + n] for d in datas):
                        use(a, n, {"command": c.name, "packet": k, "offset": b})
                        c.notes.append(f"bytes {b}-{b + n - 1}" + (f" of packet {k + 1}" if k else "")
                                       + f" repeat bytes {a}-{a + n - 1} of the reply to handshake step "
                                       f"{i + 1} (frame {s['reply_frame']}): a session token or device id; "
                                       "the driver copies them from the live reply")
        s["tokens"] = sorted(tokens.values(), key=lambda t: t["reply_offset"])
    for i, s in enumerate(steps):
        if reps[i]:
            vary = taken[i] | skip_r(i)
            s["expect"] = " ".join("??" if k in vary else f"{b:02x}" for k, b in enumerate(reps[i]))
    return steps
