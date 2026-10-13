"""Per-action diffing and protocol inference. Every claim carries frame evidence.

Byte roles: const, command, value (linear, 8/16-bit LE/BE), lookup (value->byte table),
counter (increments per message), checksum (sum/xor/CRC8/CRC16), unknown.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict

from .actions import commands_of
from .checksums import CHECKSUMS, compute
from .model import Action, Transfer


@dataclass
class Field:
    offset: int
    kind: str                 # const | command | value | lookup | counter | checksum | unknown
    width: int = 1
    endian: str = "le"
    const: int | None = None
    index: int = 0            # which number of the action label drives this field
    scale: float | None = None
    bias: float | None = None
    table: dict | None = None
    step: int | None = None
    algo: str | None = None
    covers: tuple[int, int] | None = None
    observed: list = field(default_factory=list)
    frames: list[int] = field(default_factory=list)

    def describe(self) -> str:
        w = f"u16{self.endian} " if self.width == 2 else ""
        if self.kind in ("const", "command"):
            return f"0x{self.const:02x}"
        if self.kind == "value":
            v = "value" if self.index == 0 else f"value[{self.index}]"
            return f"{w}round({v} * {self.scale:g} + {self.bias:g})"
        if self.kind == "lookup":
            return "lookup " + ", ".join(f"{k:g}→0x{v:02x}" for k, v in sorted(self.table.items()))
        if self.kind == "counter":
            return f"counter (+{self.step} per message)"
        if self.kind == "checksum":
            return f"{w}{self.algo}(bytes[{self.covers[0]}:{self.covers[1]}])"
        return "?"


def _put(b: bytearray, f: Field, v: int):
    v &= (1 << (8 * f.width)) - 1
    b[f.offset:f.offset + f.width] = v.to_bytes(f.width, "little" if f.endian == "le" else "big")


def _get(d: bytes, off: int, width: int, endian: str) -> int:
    return int.from_bytes(d[off:off + width], "little" if endian == "le" else "big")


@dataclass
class Command:
    name: str
    endpoint: int
    xfer_type: int
    setup: bytes | None
    length: int
    fields: list[Field]
    confidence: float
    frames: list[int]
    samples: list[tuple[str, str, int]]
    notes: list[str] = field(default_factory=list)

    @property
    def arity(self) -> int:
        idx = [f.index for f in self.fields if f.kind in ("value", "lookup")]
        return max(idx) + 1 if idx else 0

    def template(self) -> bytes:
        b = bytearray(self.length)
        for f in self.fields:
            if f.kind in ("const", "command"):
                b[f.offset] = f.const
        return bytes(b)

    def encode(self, *values, seq: int = 0) -> bytes:
        b = bytearray(self.template())
        for f in self.fields:
            if f.kind == "value":
                _put(b, f, int(round(values[f.index] * f.scale + f.bias + 1e-9)))
            elif f.kind == "lookup":
                _put(b, f, f.table[float(values[f.index])])
            elif f.kind == "counter":
                _put(b, f, seq * f.step)
        for f in self.fields:
            if f.kind == "checksum":
                _put(b, f, compute(f.algo, b[f.covers[0]:f.covers[1]]))
        return bytes(b)


@dataclass
class Protocol:
    vid: int | None
    pid: int | None
    commands: list[Command]
    unmatched: list[str] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        for c in d["commands"]:
            c["setup"] = c["setup"].hex() if c["setup"] else None
        return d


def _fit_linear(xs, ys):
    n = len(xs)
    if n < 2 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    b = my - a * mx
    for tol in (0, 1):
        for ca in (round(a), round(a, 1), round(a, 2), round(a, 3), round(a, 4)):
            for cb in (round(b), round(b, 2), b):
                if all(abs(round(x * ca + cb + 1e-9) - y) <= tol for x, y in zip(xs, ys)):
                    return float(ca), float(cb)
    return None


def infer(actions: list[Action], vid: int | None = None, pid: int | None = None) -> Protocol:
    # background: identical OUT payloads present in >= 80% of actions
    seen = Counter()
    for a in actions:
        for p in {(t.key(), t.data) for t in commands_of(a)}:
            seen[p] += 1
    bg = {p for p, c in seen.items() if len(actions) > 2 and c >= 0.8 * len(actions)}

    groups: dict[str, list[tuple[Action, Transfer]]] = defaultdict(list)
    unmatched = []
    for a in actions:
        msgs = [t for t in commands_of(a) if (t.key(), t.data) not in bg]
        if not msgs:
            unmatched.append(a.label)
            continue
        groups[a.name if not a.values or len(a.values) == 1 else _name(a)].append((a, msgs[0]))

    counters = _find_counters([(n, t) for n, items in groups.items() for _, t in items])

    commands = []
    for name, items in groups.items():
        keys = Counter((t.key(), len(t.data)) for _, t in items)
        (key, length), _ = keys.most_common(1)[0]
        ok = [(a, t) for a, t in items if (t.key(), len(t.data)) == (key, length)]
        notes = []
        if len(ok) < len(items):
            notes.append(f"{len(items) - len(ok)} action(s) used a different endpoint/length and were ignored")
        commands.append(_infer_command(name, ok, length, notes, counters.get(key, {})))

    # command-id bytes: const positions whose value differs between commands on the same channel
    by_chan = defaultdict(list)
    for c in commands:
        by_chan[(c.endpoint, c.xfer_type, c.setup[:4] if c.setup else None)].append(c)
    for cs in by_chan.values():
        if len(cs) < 2:
            continue
        for off in range(min(c.length for c in cs)):
            fs = [next((f for f in c.fields if f.offset == off), None) for c in cs]
            if all(f is not None and f.kind == "const" for f in fs) and len({f.const for f in fs}) > 1:
                for f in fs:
                    f.kind = "command"
    return Protocol(vid, pid, commands, unmatched)


def _name(a: Action) -> str:
    from .model import split_values
    return split_values(a.label)[0]


def _find_counters(msgs: list[tuple[str, Transfer]]) -> dict:
    """Offsets that increase by a fixed step on every message of a channel, across >= 2 commands.

    (With a single command, a steadily increasing byte is indistinguishable from a value
    recorded in increasing order, so we only call it a counter when it spans commands.)
    """
    out = {}
    by_key = defaultdict(list)
    names = defaultdict(set)
    for n, t in msgs:
        by_key[t.key()].append(t)
        names[t.key()].add(n)
    for key, ts in by_key.items():
        ts.sort(key=lambda t: t.frame)
        if len(ts) < 4 or len(names[key]) < 2:
            continue
        found = {}
        for off in range(min(len(t.data) for t in ts)):
            col = [t.data[off] for t in ts]
            steps = {(b - a) & 0xFF for a, b in zip(col, col[1:])}
            if len(steps) == 1 and 0 not in steps:
                found[off] = (steps.pop(), [t.frame for t in ts])
        out[key] = found
    return out


def _infer_command(name, items, length, notes, counters) -> Command:
    t0 = items[0][1]
    frames = [t.frame for _, t in items]
    datas = [t.data for _, t in items]
    vals = [a.values for a, _ in items]
    arity = max((len(v) for v in vals), default=0)
    fields: list[Field] = []
    for off in range(length):
        col = [d[off] for d in datas]
        f = Field(off, "unknown", observed=list(zip([v[:] for v in vals], col)), frames=frames)
        if len(set(col)) == 1:
            f.kind, f.const = "const", col[0]
        fields.append(f)
    for off, (step, fr) in counters.items():
        if off < length and fields[off].kind == "unknown":
            fields[off].kind, fields[off].step, fields[off].frames = "counter", step, fr

    def free(a, w=1):
        return a + w <= length and all(fields[i].kind == "unknown" for i in range(a, a + w))

    def claim(f: Field):
        fields[f.offset] = f
        for i in range(f.offset + 1, f.offset + f.width):
            fields[i] = Field(i, "part", const=f.offset)

    # 1. checksums (need >= 2 distinct packets)
    if len(set(datas)) >= 2:
        for off in range(length):
            done = False
            for algo, (w, _) in CHECKSUMS.items():
                if done or not free(off, w):
                    continue
                for end in ("le", "be") if w == 2 else ("le",):
                    for a, b in ((0, off), (1, off), (2, off), (off + w, length)):
                        if b - a < 2 or all(fields[i].kind == "const" for i in range(a, b)):
                            continue
                        if all(compute(algo, d[a:b]) == _get(d, off, w, end) for d in datas):
                            claim(Field(off, "checksum", w, end, algo=algo, covers=(a, b), frames=frames))
                            done = True
                            break
                    if done:
                        break

    # 2. values: 16-bit pairs where both bytes vary, then 8-bit, then lookup tables
    for j in range(arity):
        xs = [v[j] if j < len(v) else None for v in vals]
        if any(x is None for x in xs):
            continue
        for off in range(length - 1):
            if not free(off, 2):
                continue
            for end in ("le", "be"):
                ys = [_get(d, off, 2, end) for d in datas]
                fit = _fit_linear(xs, ys)
                if fit and all(len({d[i] for d in datas}) > 1 for i in (off, off + 1)):
                    claim(Field(off, "value", 2, end, index=j, scale=fit[0], bias=fit[1], frames=frames))
                    break
        for off in range(length):
            if free(off):
                fit = _fit_linear(xs, [d[off] for d in datas])
                if fit:
                    claim(Field(off, "value", index=j, scale=fit[0], bias=fit[1], frames=frames))
    for j in range(arity):
        xs = [v[j] if j < len(v) else None for v in vals]
        if any(x is None for x in xs) or len(set(xs)) < 2:
            continue
        for off in range(length):
            if not free(off):
                continue
            table = {}
            if all(table.setdefault(float(x), d[off]) == d[off] for x, d in zip(xs, datas)) \
                    and len(set(table.values())) == len(table):
                claim(Field(off, "lookup", index=j, table=table, frames=frames))
    fields = [f for f in fields if f.kind != "part"]

    unknown = sum(f.kind == "unknown" for f in fields)
    conf = 1.0 - unknown / max(length, 1)
    if len(items) < 3:
        conf *= 0.6
        notes.append("fewer than 3 samples: record more values of this action to raise confidence")
    if any(f.kind == "lookup" for f in fields):
        notes.append("lookup tables only cover the values that were captured")
    if unknown:
        notes.append(f"{unknown} byte(s) vary but could not be explained")
    return Command(name, t0.endpoint, t0.xfer_type, t0.setup, length, fields, round(conf, 2),
                   frames, [(a.label, t.data.hex(" "), t.frame) for a, t in items], notes)
