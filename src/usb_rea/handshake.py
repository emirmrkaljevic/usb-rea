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

Retries: when the app sends the same message again straight away (identical channel and bytes, nothing
else sent in between but background polls), because the first copy got no reply or a different (busy/not ready) one, the
copies are one step. The step keeps the reply to the last copy and lists the earlier copies under
`retries`, so the driver resends a step that times out or answers differently, as many times as the
app did.

Reopens: when the app sends the whole handshake again later in the capture (after the device slept,
was replugged, or the app reconnected), that later block is the same session setup, not an action.
Each later message must match its step on the same channel and length, differing only in the
request checksum or in bytes copied from the block's own replies (a new session token). The block
is set aside before actions are inferred and listed under `reopens` on each step.

Branches: a later block may follow the handshake up to some step and then send other messages,
when the reply to that step differs at a byte that is not a session token or checksum (a status or
mode the device reports, such as "ready" or "needs calibration"). That step branches on the reply
byte: its `branches` map each value seen there to the steps the app sent next (the rest of the
handshake for the first session's value, the other messages for the others, up to the next action
marker). The driver reads the live reply byte and takes the matching branch, falling back to the
most common one for a value the capture never showed. One branch point per handshake, on one byte.
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


def _query(t: Transfer) -> bool:
    return bool((t.is_out and t.data) or is_control_read(t))


def _group(qs: list[Transfer], ordered: list[Transfer], frames: list[int], polls: set) -> list[list[Transfer]]:
    """Consecutive identical copies (nothing else sent in between but polls) are retries of one step."""
    def between(a, b):
        return [x for x in ordered[bisect_right(frames, a.frame):bisect_right(frames, b.frame) - 1]
                if _query(x) and id(x) not in polls]
    groups: list[list[Transfer]] = []
    for t in qs:
        prev = groups[-1][-1] if groups else None
        if prev is not None and (prev.key(), prev.data) == (t.key(), t.data) and not between(prev, t):
            groups[-1].append(t)
        else:
            groups.append([t])
    return groups[:MAX_STEPS]


def _setup(transfers, background, marks):
    starts = [m["start"] for m in marks if not is_observation(m["label"])]
    if not starts:
        return None
    polls = set().union(*(b["ids"] for b in background)) if background else set()
    ordered = sorted(transfers, key=lambda t: t.frame)
    return min(starts), polls, ordered, [t.frame for t in ordered]


def _same_step(m: Transfer, c: Transfer, replies: list[bytes], ck: dict | None) -> bool:
    """m is step c sent again: same channel and length, other bytes only checksum or copied from replies."""
    if m.key() != c.key() or len(m.data or b"") != len(c.data or b"") or is_control_read(m) != is_control_read(c):
        return False
    diff = {k for k, (a, b) in enumerate(zip(m.data or b"", c.data or b"")) if a != b}
    if not diff:
        return True
    ok = set()
    if ck and not is_control_read(m) and int.from_bytes(m.data[-ck["width"]:], "little" if ck["endian"] == "le"
                                                         else "big") == compute(ck["algo"], m.data[ck["start"]:len(m.data) - ck["width"]]):
        ok |= _ck_span(ck, len(m.data))
    for r in replies:
        for _, b, n in _runs(r, m.data, set(), set()):
            ok |= set(range(b, b + n))
    return diff <= ok


class Block(list):
    """Copies of each step of a later handshake block. `fork` is set when the block took another branch:
    {"step": index of the step whose reply decided it, "offset": reply byte, "value": its value}; the
    copies after that step are the messages the app sent instead of the rest of the handshake."""
    fork: dict | None = None


def _copies(after: list[Transfer], q: int) -> tuple[list[Transfer], int]:
    """after[q] and the identical copies sent straight after it (retries); returns them and the last index."""
    copies = [after[q]]
    while q + 1 < len(after) and (after[q + 1].key(), after[q + 1].data) == (after[q].key(), after[q].data) \
            and after[q + 1].ts - after[q].ts <= WINDOW:
        q += 1
        copies.append(after[q])
    return copies, q


def _reused(reply: bytes, reqs: list[bytes]) -> set[int]:
    """Reply bytes copied into later requests (session tokens)."""
    return {k for m in reqs for a, _, n in _runs(reply, m, set(), set()) for k in range(a, a + n)}


def _decides(pre_reply: bytes, reply: bytes, ck: dict | None, pre_later: list[bytes], later: list[bytes]) -> int | None:
    """First byte where a block's reply differs from the first session's, not counting checksum and token bytes."""
    if not pre_reply or len(pre_reply) != len(reply):
        return None
    skip = _ck_span(ck, len(reply)) | _reused(pre_reply, pre_later) | _reused(reply, later)
    diff = [k for k, (a, b) in enumerate(zip(pre_reply, reply)) if a != b and k not in skip]
    return diff[0] if diff else None


def find_reopens(transfers: list[Transfer], background: list[dict], marks: list[dict]) -> list[Block]:
    """Later blocks that send the pre-action sequence again: one list of copies per step. A block that
    follows it up to a step whose reply differs, then sends other messages, is a branch (Block.fork)."""
    st = _setup(transfers, background, marks)
    if not st:
        return []
    first, polls, ordered, frames = st
    acts = [(m["start"], m.get("end", m["start"])) for m in marks if not is_observation(m["label"])]
    starts = sorted(a for a, _ in acts)
    pre = _group([t for t in ordered if t.ts < first and _query(t) and id(t) not in polls], ordered, frames, polls)
    if len(pre) < 2:
        return []
    ck = _checksum([g[-1].data for g in pre if not is_control_read(g[-1])])
    pre_reps = []
    for g in pre:
        r = _reply(g[-1], ordered, frames)
        pre_reps.append(r.data if r else b"")
    rck = _checksum(pre_reps)
    after = [t for t in ordered if t.ts >= first and _query(t) and id(t) not in polls]
    blocks, p = [], 0
    while p < len(after):
        if (after[p].key(), after[p].data) != (pre[0][-1].key(), pre[0][-1].data):
            p += 1
            continue
        block, replies, q = Block(), [], p
        for c in (g[-1] for g in pre):
            if q >= len(after) or not _same_step(after[q], c, replies, ck):
                break
            copies, q = _copies(after, q)
            r = _reply(copies[-1], ordered, frames)
            replies.append(r.data if r else b"")
            block.append(copies)
            q += 1
        if len(block) == len(pre):
            blocks.append(block)
            p = q
            continue
        # a branch: the app went on with other messages, up to the next action marker
        # (only between actions: inside one, the messages belong to that action)
        end = next((s for s in starts if s > after[p].ts), float("inf"))
        inside = any(a <= after[p].ts <= z for a, z in acts)
        tail = []
        while block and not inside and q < len(after) and after[q].ts < end and len(block) + len(tail) < MAX_STEPS:
            copies, q = _copies(after, q)
            tail.append(copies)
            q += 1
        k = len(block) - 1
        off = _decides(pre_reps[k], replies[k], rck, [g[-1].data for g in pre[k + 1:]],
                       [c[-1].data for c in tail]) if block and tail else None
        if off is None:
            p += 1
            continue
        blocks.append(Block(block + tail))
        blocks[-1].fork = {"step": k, "offset": off, "value": replies[k][off]}
        p = q
    return blocks


def reopen_ids(blocks, transfers) -> set[int]:
    """ids of the requests and replies of reopen blocks, to set aside before actions are inferred."""
    ordered = sorted(transfers, key=lambda t: t.frame)
    frames = [t.frame for t in ordered]
    out = set()
    for b in blocks:
        for copies in b:
            for c in copies:
                out.add(id(c))
                r = _reply(c, ordered, frames)
                if r is not None:
                    out.add(id(r))
    return out


def find_handshake(transfers: list[Transfer], background: list[dict], marks: list[dict],
                   commands: list = (), t0: float = 0.0, reopens: list | None = None) -> list[dict]:
    """Handshake steps (dicts, JSON-ready) found before the first action marker."""
    st = _setup(transfers, background, marks)
    if not st:
        return []
    first, polls, ordered, frames = st
    reopens = find_reopens(transfers, background, marks) if reopens is None else reopens
    again = {id(c) for b in reopens for copies in b for c in copies}
    later = {(t.key(), t.data) for t in ordered if t.ts >= first and _query(t) and id(t) not in again}
    qs = [t for t in ordered if t.ts < first and _query(t) and id(t) not in polls
          and (t.key(), t.data) not in later]
    groups = _group(qs, ordered, frames, polls)
    pre = _group([t for t in ordered if t.ts < first and _query(t) and id(t) not in polls], ordered, frames, polls)
    where = {id(g[-1]): k for k, g in enumerate(pre)}
    steps = []
    for i, g in enumerate(groups, 1):
        q = g[-1]
        r = _reply(q, ordered, frames)
        tries = []
        for c in g[:-1]:
            cr = _reply(c, ordered, frames)
            tries.append({"frame": c.frame, "time": round(c.ts - t0, 3), "reply": cr.data.hex(" ") if cr else None})
        steps.append({
            "step": i, "frame": q.frame, "time": round(q.ts - t0, 3),
            "endpoint": q.endpoint, "xfer_type": q.xfer_type, "setup": q.setup.hex() if q.setup else None,
            "read": is_control_read(q), "request": q.data.hex(" "),
            "reply": r.data.hex(" ") if r else None, "reply_frame": r.frame if r else None,
            "reply_endpoint": r.endpoint if r else None, "reply_xfer_type": r.xfer_type if r else None,
            "latency_ms": round((r.ts - q.ts) * 1000, 1) if r else None,
            "request_checksum": None, "reply_checksum": None, "uses": [], "tokens": [], "echoes": [],
            "expect": None, "retries": tries,
            "reopens": [{"frame": b[where[id(q)]][-1].frame, "time": round(b[where[id(q)]][-1].ts - t0, 3)}
                        for b in reopens if id(q) in where and (not b.fork or where[id(q)] <= b.fork["step"])],
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
    _branches(steps, groups, reopens, where, ordered, frames, t0, qck, rck)
    return steps


def _fits(ck: dict | None, m: bytes) -> bool:
    return bool(ck and m and len(m) >= ck["start"] + ck["width"] + 2 and int.from_bytes(
        m[-ck["width"]:], "little" if ck["endian"] == "le" else "big") == compute(ck["algo"], m[ck["start"]:len(m) - ck["width"]]))


def _branches(steps, groups, reopens, where, ordered, frames, t0, qck, rck) -> None:
    """Record on the deciding step which messages the app sent next for each value of its reply byte."""
    forks = [b for b in reopens if b.fork]
    if not forks:
        return
    pos = {where[id(g[-1])]: k for k, g in enumerate(groups) if id(g[-1]) in where}   # pre index -> step index
    fork = forks[0].fork
    k = pos.get(fork["step"])
    if k is None or not steps[k]["reply"]:
        return
    s, off = steps[k], fork["offset"]
    main = bytes.fromhex(s["reply"])
    if len(main) <= off:
        return
    cases = {f"{main[off]:02x}": {"count": 1, "main": True, "frames": [s["reply_frame"]], "steps": []}}
    for b in reopens:
        if b.fork and (b.fork["step"], b.fork["offset"]) != (fork["step"], off):
            continue
        dq = b[fork["step"]][-1]
        r = _reply(dq, ordered, frames)
        if r is None or len(r.data) <= off:
            continue
        case = cases.setdefault(f"{r.data[off]:02x}", {"count": 0, "main": not b.fork, "frames": [], "steps": []})
        case["count"] += 1
        case["frames"].append(r.frame)
        if b.fork and not case["steps"] and not case["main"]:
            # this session's replies so far, indexed like the driver's session list (step n -> n - 1)
            session = []
            for i in range(k + 1):
                c = b[where[id(groups[i][-1])]][-1] if id(groups[i][-1]) in where else None
                cr = _reply(c, ordered, frames) if c is not None else None
                session.append(cr.data if cr else b"")
            case["steps"] = _tail(b[fork["step"] + 1:], session, k + 1, ordered, frames, t0, qck, rck)
    s["expect"] = " ".join("??" if i == off else x for i, x in enumerate(s["expect"].split()))
    s["branches"] = {"offset": off, "default": max(cases, key=lambda v: cases[v]["count"]), "cases": cases}


def _tail(groups, session, done, ordered, frames, t0, qck, rck) -> list[dict]:
    """Steps (numbered after the `done` steps before them) the app sent in one branch, with their replies."""
    out = []
    for j, g in enumerate(groups):
        q = g[-1]
        r = _reply(q, ordered, frames)
        req, rep = q.data or b"", r.data if r else b""
        qc, rc = qck if not is_control_read(q) and _fits(qck, req) else None, rck if _fits(rck, rep) else None
        skip = _ck_span(qc, len(req))
        uses = []
        for i, prev in enumerate(session):
            for a, b, n in _runs(prev, req, set(), skip):
                if not any(b < u["offset"] + u["width"] and u["offset"] < b + n for u in uses):
                    uses.append({"step": i + 1, "reply_offset": a, "offset": b, "width": n})
        out.append({
            "step": done + j + 1, "frame": q.frame, "time": round(q.ts - t0, 3),
            "endpoint": q.endpoint, "xfer_type": q.xfer_type, "setup": q.setup.hex() if q.setup else None,
            "read": is_control_read(q), "request": req.hex(" "),
            "reply": rep.hex(" ") if r else None, "reply_frame": r.frame if r else None,
            "reply_endpoint": r.endpoint if r else None, "reply_xfer_type": r.xfer_type if r else None,
            "request_checksum": {**qc, "covers": [qc["start"], len(req) - qc["width"]]} if qc else None,
            "reply_checksum": {**rc, "covers": [rc["start"], len(rep) - rc["width"]]} if rc else None,
            "uses": uses, "retries": [{"frame": c.frame} for c in g[:-1]], "expect": None,
        })
        session.append(rep)
    for i, st in enumerate(out):
        if st["reply"]:
            rep = bytes.fromhex(st["reply"])
            n = done + i   # this reply's index in the session
            vary = _ck_span(st["reply_checksum"], len(rep)) | {
                u["reply_offset"] + x for o in out for u in o["uses"] if u["step"] == n + 1 for x in range(u["width"])}
            st["expect"] = " ".join("??" if k in vary else f"{b:02x}" for k, b in enumerate(rep))
    return out
