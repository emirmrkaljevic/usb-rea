"""Device replies: pair host->device queries with the device->host data that answers them.

A query is a host->device message (bulk/interrupt OUT, control SET_REPORT/vendor OUT) or a
class/vendor control IN request (GET_REPORT). Its reply is the IN data that follows it:
the completion of the same control request, or a bulk/interrupt IN transfer shortly after.

Pairing runs in two passes. Pass 1 takes, for every query, the first IN transfer before the next
host->device message; that tells which query groups get replies at all, on which endpoint, of
what length and after what typical delay. Pass 2 assigns each IN transfer of such a shape to the
outstanding query whose delay is closest to its group's typical delay, so a poll that lands
between a command and the command's reply does not steal it.

Reply bytes are explained with the same machinery as commands (constants, checksums, linear fits
to label values with the leave-one-out guard), plus echo (repeats a query byte), counter, and
reading (varies on its own; reported with its observed range, nothing more is claimed).
"""
from __future__ import annotations
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from statistics import median

from .infer import Command, Field, _infer_command, _get
from .model import Action, Transfer

WINDOW = 0.5  # seconds: a reply later than this is not paired
MAX_REPLY = 64  # longer IN transfers are bulk data (sectors, frames), not answers to a query


@dataclass
class Response:
    query: str                    # command name, "poll N" or "GET_REPORT ..."
    source: str                   # command | background | control read
    query_endpoint: int
    query_xfer_type: int
    query_setup: bytes | None
    query_payload: str            # query bytes, '??' where they vary
    endpoint: int                 # IN endpoint the reply arrives on
    xfer_type: int
    length: int
    fields: list[Field]
    answered: int
    queries: int
    latency_ms: float
    samples: list[tuple[str, int, str, int]]   # (label, query frame, reply hex, reply frame)
    packet: int = 0               # which packet of a multi-packet command it answers
    request: Command | None = None  # how to send the query again (background polls)
    notes: list[str] = field(default_factory=list)

    @property
    def explained(self) -> int:
        return sum(f.width for f in self.fields if f.kind not in ("reading", "unknown"))


def is_control_read(t: Transfer) -> bool:
    """Class or vendor control IN request (GET_REPORT, vendor reads); standard requests are skipped."""
    return t.is_in and t.xfer_type == 2 and t.setup is not None and not t.data and (t.setup[0] >> 5) & 3 in (1, 2)


def _shape(t: Transfer) -> tuple:
    return (t.endpoint, t.xfer_type, len(t.data))


def pair(groups: dict, transfers: list[Transfer], window: float = WINDOW) -> dict:
    """groups: name -> list of query transfers. Returns name -> (shape, [(query, reply|None)], median latency s)
    for the groups that get replies (at least 2 and at least half of their queries answered)."""
    ordered = sorted(transfers, key=lambda t: t.frame)
    frames = [t.frame for t in ordered]
    out = {}
    # control reads: the reply is the completion of the same request (EP0 transfers are serialised)
    reads = {n: qs for n, qs in groups.items() if qs and is_control_read(qs[0])}
    for name, qs in reads.items():
        pairs = []
        for q in qs:
            r = None
            for j in range(bisect_right(frames, q.frame), len(ordered)):
                t = ordered[j]
                if t.ts - q.ts > window:
                    break
                if t.xfer_type == 2 and t.is_in and t.data and t.setup is None:
                    r = t
                    break
            pairs.append((q, r))
        got = [(q, r) for q, r in pairs if r is not None]
        shape = Counter(_shape(r) for _, r in got).most_common(1)[0][0] if got else None
        got = [(q, r) for q, r in got if _shape(r) == shape]
        if len(got) >= 2 and len(got) >= 0.5 * len(qs) and shape[2] <= MAX_REPLY:
            pairs = [(q, r if r is not None and _shape(r) == shape else None) for q, r in pairs]
            out[name] = (shape, pairs, median(r.ts - q.ts for q, r in got))

    # pass 1: queries sent back to back (no IN in between) form a run. A run of one takes the first IN
    # transfer before the next host->device message; a longer run is paired in order, but only when it
    # is followed by exactly as many IN transfers (otherwise it is left out of the statistics)
    ins = [t for t in ordered if t.is_in and t.data and t.xfer_type != 2]
    in_frames = [t.frame for t in ins]
    outs = [t for t in ordered if t.is_out and t.data]
    first, decided = {}, set()
    i = 0
    while i < len(outs):
        run = [outs[i]]
        nxt = bisect_right(in_frames, outs[i].frame)
        while i + len(run) < len(outs) and (nxt >= len(ins) or outs[i + len(run)].frame < ins[nxt].frame):
            run.append(outs[i + len(run)])
        i += len(run)
        stop = outs[i].frame if i < len(outs) else None
        after = [r for r in ins[nxt:nxt + len(run) + 1] if stop is None or r.frame < stop]
        if len(run) == 1:
            after = after[:1]
        elif len(after) != len(run):
            continue
        decided |= {id(q) for q in run}
        for q, r in zip(run, after):
            if r.ts - q.ts <= window:
                first[id(q)] = r
    replying = {}
    for name, qs in groups.items():
        if name in reads or not qs:
            continue
        shapes = Counter(_shape(first[id(q)]) for q in qs if id(q) in first)
        if not shapes:
            continue
        shape, n = shapes.most_common(1)[0]
        if n >= 2 and n >= 0.5 * sum(id(q) in decided for q in qs) and shape[2] <= MAX_REPLY:
            lat = median(first[id(q)].ts - q.ts for q in qs if id(q) in first and _shape(first[id(q)]) == shape)
            replying[name] = (shape, lat)

    # pass 2: each reply goes to the outstanding query whose delay best matches its group's typical delay
    queries = sorted(((q, n) for n in replying for q in groups[n]), key=lambda x: x[0].frame)
    shapes = {s for s, _ in replying.values()}
    got: dict[int, Transfer] = {}
    pending: list[tuple[Transfer, str]] = []
    qi = 0
    for r in ins:
        if _shape(r) not in shapes:
            continue
        while qi < len(queries) and queries[qi][0].frame < r.frame:
            pending.append(queries[qi])
            qi += 1
        pending = [(q, n) for q, n in pending if r.ts - q.ts <= window and id(q) not in got]
        best = None
        for q, n in pending:
            shape, lat = replying[n]
            if shape != _shape(r):
                continue
            err = abs((r.ts - q.ts) - lat)
            if err <= max(4 * lat, 0.05) and (best is None or err < best[0]):
                best = (err, q)
        if best:
            got[id(best[1])] = r
    for name, (shape, lat) in replying.items():
        pairs = [(q, got.get(id(q))) for q in groups[name]]
        done = [(q, r) for q, r in pairs if r is not None]
        if len(done) >= 2:
            out[name] = (shape, pairs, median(r.ts - q.ts for q, r in done))
    return out


def _pattern(datas: list[bytes]) -> str:
    n = min(len(d) for d in datas)
    return " ".join(f"{datas[0][i]:02x}" if len({d[i] for d in datas}) == 1 else "??" for i in range(n))


def decode(name: str, source: str, pairs: list, shape: tuple, latency: float,
           labels: dict[int, str] | None = None, packet: int = 0, driven: set[int] = frozenset()) -> Response:
    """Infer the byte roles of one group's replies. labels: query frame -> action label;
    driven: query offsets that carry the label value (a reply byte copying those is fitted, not echoed)."""
    labels = labels or {}
    got = sorted([(q, r) for q, r in pairs if r is not None], key=lambda p: p[1].frame)
    q0 = got[0][0]
    length = shape[2]
    notes: list[str] = []
    acts = [Action(labels.get(q.frame, ""), 0, 0) for q, _ in got]
    items = list(zip(acts, [r for _, r in got]))
    labelled = any(a.values for a in acts)
    datas = [r.data for _, r in got]
    qdatas = [q.data for q, _ in got]
    frames = [r.frame for _, r in got]
    qlen = min((len(d) for d in qdatas), default=0)

    def echo_of(o, skip=()):
        for k in range(qlen):
            if k not in skip and len({d[k] for d in qdatas}) > 1 and all(r[o] == q[k] for q, r in zip(qdatas, datas)):
                return k
        return None

    # echo of a sequence number or other non-label byte: claimed before fitting, so a counter that
    # happens to rise with the values is not mistaken for one
    preset = {}
    for o in range(length):
        k = echo_of(o, driven)
        if k is not None:
            preset[o] = Field(o, "echo", echo=k, frames=frames)
    c = _infer_command(name, items, length, [], {}, lookups=False, preset=preset)
    by_off = {f.offset: f for f in c.fields}
    covered = {i for f in c.fields for i in range(f.offset, f.offset + f.width)}

    def unknown(o):
        return o in by_off and by_off[o].kind == "unknown"

    # echo of a label-driven query byte that no fit explained
    for o in range(length):
        if unknown(o) and echo_of(o) is not None:
            by_off[o] = Field(o, "echo", echo=echo_of(o), frames=frames)
    # counter: steps by the same non-zero amount from one reply to the next
    if len(datas) >= 4:
        for o in range(length):
            if unknown(o):
                steps = {(b[o] - a[o]) & 0xFF for a, b in zip(datas, datas[1:])}
                if len(steps) == 1 and 0 not in steps:
                    by_off[o] = Field(o, "counter", step=steps.pop(), frames=frames)
    # readings: whatever still varies. Two neighbouring bytes are read as one 16-bit number only when
    # one byte order changes smoothly and the other jumps (needs 8+ replies)
    o = 0
    while o < length:
        if not unknown(o):
            o += 1
            continue
        width, end = 1, "le"
        if unknown(o + 1) and len(datas) >= 8:
            tv = {e: sum(abs(_get(b, o, 2, e) - _get(a, o, 2, e)) for a, b in zip(datas, datas[1:])) for e in ("le", "be")}
            for e, other in (("le", "be"), ("be", "le")):
                if tv[e] * 8 < tv[other]:
                    width, end = 2, e
        vals = [_get(d, o, width, end) for d in datas]
        by_off[o] = Field(o, "reading", width, end, limits=(min(vals), max(vals)), frames=frames)
        if width == 2:
            del by_off[o + 1]
        o += width
    fields = [by_off[k] for k in sorted(by_off)]
    for f in fields:
        f.observed, f.frames = [], f.frames[:20]
    readings = [f for f in fields if f.kind == "reading"]
    if readings:
        where = ("byte " if len(readings) == 1 and readings[0].width == 1 else "bytes ") + ", ".join(
            f"{f.offset}" + (f"-{f.offset + 1}" if f.width == 2 else "") for f in readings)
        if labelled:
            notes.append(f"{where} vary but do not follow the action values; they are listed as readings "
                         "(meaning unknown, only the observed range is given)")
        else:
            notes.append(f"{where} vary with no label to explain them: listed as readings with their observed "
                         "range; label actions with the value the vendor app shows (e.g. 'fan 1200') to fit them")
        if any(f.width == 2 for f in readings):
            notes.append("16-bit readings: byte order chosen because that order changes smoothly between replies "
                         "and the other jumps")
    if len(got) < 3:
        notes.append("fewer than 3 replies: record more to raise confidence")
    missing = len(pairs) - len(got)
    if missing:
        notes.append(f"{missing} of {len(pairs)} queries got no reply of this shape within {WINDOW:g} s")
    samples = [(labels.get(q.frame, ""), q.frame, r.data.hex(" "), r.frame) for q, r in got[:20]]
    payload = _pattern(qdatas) if qdatas and qlen else ""
    return Response(name, source, q0.endpoint, q0.xfer_type, q0.setup, payload, shape[0], shape[1], length,
                    fields, len(got), len(pairs), round(latency * 1000, 1), samples, packet, None, notes)


def link_command_ids(responses: list[Response], qconsts: dict[str, dict[int, int]]):
    """A constant reply byte that equals a constant query byte, with different values for different
    queries on the same reply endpoint, is an echoed command id."""
    by_ep = defaultdict(list)
    for r in responses:
        if r.query in qconsts:
            by_ep[r.endpoint].append(r)
    for rs in by_ep.values():
        if len(rs) < 2:
            continue
        for o in range(max(r.length for r in rs)):
            hit = [(r, f) for r in rs for f in r.fields if f.offset == o and f.kind == "const"]
            if len(hit) < 2 or len({f.const for _, f in hit}) < 2:
                continue
            ks = set.intersection(*({k for k, v in qconsts[r.query].items() if v == f.const} for r, f in hit))
            fs = [f for _, f in hit]
            if ks:
                for f in fs:
                    f.kind, f.echo = "echo", min(ks)


def query_command(name: str, qs: list[Transfer]) -> Command:
    """Explain a background poll's own bytes (constant, sequence counter, checksum) so a driver can send it."""
    qs = sorted(qs, key=lambda t: t.frame)
    n = min(len(t.data) for t in qs)
    qs = [t for t in qs if len(t.data) == n]
    # checksums first: a sum over a +1 sequence byte also counts up by one
    c = _infer_command(name, [(Action(name, 0, 0), t) for t in qs], n, [], {}, lookups=False)
    for f in c.fields:
        if f.kind == "unknown" and len(qs) >= 4:
            steps = {(b.data[f.offset] - a.data[f.offset]) & 0xFF for a, b in zip(qs, qs[1:])}
            if len(steps) == 1 and 0 not in steps:
                f.kind, f.step = "counter", steps.pop()
    for f in c.fields:
        f.observed, f.frames = [], f.frames[:20]
    c.frames, c.samples, c.notes = c.frames[:20], c.samples[:5], []
    return c


def analyze_responses(transfers: list[Transfer], commands: list[Command], background: list[dict]) -> list[Response]:
    """Find and decode the replies to inferred commands, background polls and control reads."""
    by_frame = {t.frame: t for t in transfers}
    groups: dict[str, list[Transfer]] = {}
    meta: dict[str, tuple] = {}
    for c in commands:
        for j, step in enumerate([c, *c.steps]):
            qs = [by_frame[fr] for _, _, fr in step.samples if fr in by_frame]
            if qs:
                key = f"{c.name}\x00{j}"
                groups[key] = qs
                driven = {i for f in step.fields if f.kind in ("value", "bitfield", "lookup")
                          for i in range(f.offset, f.offset + f.width)}
                meta[key] = (c.name, "command", {fr: lb for lb, _, fr in step.samples}, j, driven)
    ids = {id(t): t for t in transfers}
    for i, b in enumerate(background, 1):
        qs = [ids[x] for x in b["ids"] if x in ids]
        if qs:
            groups[f"poll {i}"] = qs
            meta[f"poll {i}"] = (f"poll {i}", "background", {}, 0, set())
    reads = defaultdict(list)
    for t in transfers:
        if is_control_read(t):
            reads[t.setup].append(t)
    for setup, qs in reads.items():
        kind = {1: "Input", 2: "Output", 3: "Feature"}.get(setup[3], f"type {setup[3]}")
        name = f"GET_REPORT {kind} 0x{setup[2]:02x}" if setup[0] & 0x60 == 0x20 and setup[1] == 0x01 \
            else f"control read {setup[:4].hex()}"
        groups[name] = qs
        meta[name] = (name, "control read", {}, 0, set())

    paired = pair(groups, transfers)
    out, used = [], {}
    for key in groups:
        if key not in paired:
            continue
        name, source, labels, j, driven = meta[key]
        if name in used:
            continue  # one reply per command: the first packet of the transaction that gets one
        used[name] = key
        shape, pairs, lat = paired[key]
        r = decode(name, source, pairs, shape, lat, labels, j, driven)
        if source == "background":
            r.request = query_command(name, groups[key])
        out.append(r)
    qconsts = {}
    for name, key in used.items():
        qs = groups[key]
        if qs[0].data:
            n = min(len(t.data) for t in qs)
            qconsts[name] = {k: qs[0].data[k] for k in range(n) if len({t.data[k] for t in qs}) == 1}
    link_command_ids(out, qconsts)
    return out
