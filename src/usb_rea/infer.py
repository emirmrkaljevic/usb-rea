"""Per-action diffing and protocol inference. Every claim carries frame evidence.

Byte roles: const, command, value (linear, 8/16/32-bit LE/BE), bitfield (packed bits),
lookup (value->byte table), counter (increments per message), checksum (sum/xor/CRC8/CRC16),
unknown.
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
    kind: str                 # const | command | value | bitfield | lookup | counter | checksum | unknown
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
    source: int | None = None  # checksum over an earlier packet of the same transaction
    bit_offset: int | None = None   # LSB of packed field within the width bytes
    bit_width: int | None = None
    observed: list = field(default_factory=list)
    frames: list[int] = field(default_factory=list)

    def describe(self) -> str:
        if self.width == 4:
            w = f"u32{self.endian} "
        elif self.width == 2:
            w = f"u16{self.endian} "
        else:
            w = ""
        if self.kind in ("const", "command"):
            return f"0x{self.const:02x}"
        if self.kind == "value":
            v = "value" if self.index == 0 else f"value[{self.index}]"
            return f"{w}round({v} * {self.scale:g} + {self.bias:g})"
        if self.kind == "bitfield":
            v = "value" if self.index == 0 else f"value[{self.index}]"
            expr = f"round({v} * {self.scale:g} + {self.bias:g})"
            return f"bits[{self.bit_offset}:{self.bit_offset + self.bit_width}] = {expr}"
        if self.kind == "lookup":
            return "lookup " + ", ".join(f"{k:g}→0x{v:02x}" for k, v in sorted(self.table.items()))
        if self.kind == "counter":
            return f"counter (+{self.step} per message)"
        if self.kind == "checksum":
            src = f"packet{self.source + 1}" if self.source is not None else "bytes"
            return f"{w}{self.algo}({src}[{self.covers[0]}:{self.covers[1]}])"
        return "?"


def _put(b: bytearray, f: Field, v: int):
    v &= (1 << (8 * f.width)) - 1
    b[f.offset:f.offset + f.width] = v.to_bytes(f.width, "little" if f.endian == "le" else "big")


def _get(d: bytes, off: int, width: int, endian: str) -> int:
    return int.from_bytes(d[off:off + width], "little" if endian == "le" else "big")


def _put_bits(b: bytearray, f: Field, v: int):
    """Pack v into bits [bit_offset : bit_offset+bit_width) of the field's byte span (LE bit order)."""
    bo, bw = f.bit_offset, f.bit_width
    v &= (1 << bw) - 1
    span = int.from_bytes(b[f.offset:f.offset + f.width], "little")
    mask = ((1 << bw) - 1) << bo
    span = (span & ~mask) | (v << bo)
    b[f.offset:f.offset + f.width] = span.to_bytes(f.width, "little")


def _get_bits(d: bytes, off: int, width: int, bit_offset: int, bit_width: int) -> int:
    span = int.from_bytes(d[off:off + width], "little")
    return (span >> bit_offset) & ((1 << bit_width) - 1)


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
    steps: list["Command"] = field(default_factory=list)  # follow-up packets of a multi-packet transaction

    @property
    def arity(self) -> int:
        idx = [f.index for c in [self, *self.steps] for f in c.fields if f.kind in ("value", "bitfield", "lookup")]
        return max(idx) + 1 if idx else 0

    def template(self) -> bytes:
        b = bytearray(self.length)
        for f in self.fields:
            if f.kind in ("const", "command"):
                b[f.offset] = f.const
            elif f.kind == "bitfield" and f.const is not None:
                # plant constant bits outside the packed value (LE byte span)
                b[f.offset:f.offset + f.width] = f.const.to_bytes(f.width, "little")
        return bytes(b)

    def encode_all(self, *values, seq: int = 0) -> list[bytes]:
        """Every packet of the transaction, in order (the counter advances per packet)."""
        out: list[bytes] = []
        for i, c in enumerate([self, *self.steps]):
            out.append(c.encode(*values, seq=seq + i, prev=out))
        return out

    def encode(self, *values, seq: int = 0, prev: list[bytes] | None = None) -> bytes:
        b = bytearray(self.template())
        for f in self.fields:
            if f.kind == "value":
                _put(b, f, int(round(values[f.index] * f.scale + f.bias + 1e-9)))
            elif f.kind == "bitfield":
                _put_bits(b, f, int(round(values[f.index] * f.scale + f.bias + 1e-9)))
            elif f.kind == "lookup":
                _put(b, f, f.table[float(values[f.index])])
            elif f.kind == "counter":
                _put(b, f, seq * f.step)
        for f in self.fields:
            if f.kind == "checksum":
                src = b if f.source is None else prev[f.source]
                _put(b, f, compute(f.algo, src[f.covers[0]:f.covers[1]]))
        return bytes(b)


@dataclass
class Protocol:
    vid: int | None
    pid: int | None
    commands: list[Command]
    unmatched: list[str] = field(default_factory=list)
    hid: list[dict] = field(default_factory=list)   # filled by pipeline when the capture has HID descriptors

    def to_dict(self):
        d = asdict(self)
        for c in d["commands"]:
            for x in [c, *c["steps"]]:
                x["setup"] = x["setup"].hex() if x["setup"] else None
        return d


def _fit_linear(xs, ys):
    """Linear fit that must also survive leave-one-out (guards against rounding coincidences)."""
    fit = _fit_linear_raw(xs, ys)
    if fit is None or len(xs) < 3:
        return fit
    for i in range(len(xs)):
        sub = _fit_linear_raw(xs[:i] + xs[i + 1:], ys[:i] + ys[i + 1:])
        tol = 1 if len(xs) >= 5 else 0
        if sub is None or abs(round(xs[i] * sub[0] + sub[1] + 1e-9) - ys[i]) > tol:
            return None
    return fit


def _fit_linear_raw(xs, ys):
    n = len(xs)
    if n < 2 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    b = my - a * mx
    # off-by-one tolerance (vendor rounding) only with enough samples; otherwise a lookup table is the honest answer
    for tol in (0, 1) if n >= 5 else (0,):
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

    groups: dict[str, list[tuple[Action, list[Transfer]]]] = defaultdict(list)
    unmatched = []
    for a in actions:
        msgs = [t for t in commands_of(a) if (t.key(), t.data) not in bg]
        if not msgs:
            unmatched.append(a.label)
            continue
        groups[a.name if not a.values or len(a.values) == 1 else _name(a)].append((a, msgs))

    counters = _find_counters([(n, t) for n, items in groups.items() for _, ms in items for t in ms])

    commands = []
    for name, items in groups.items():
        # transaction shape: how many packets this action sends, and on which channels
        shapes = Counter(tuple((t.key(), len(t.data)) for t in ms) for _, ms in items)
        shape, _ = shapes.most_common(1)[0]
        ok = [(a, ms) for a, ms in items if tuple((t.key(), len(t.data)) for t in ms) == shape]
        if len(ok) < 2 and len(shape) > 1:
            # not enough identical transactions: fall back to the first packet only
            shape = (shape[0],)
            ok = [(a, ms[:1]) for a, ms in items if (ms[0].key(), len(ms[0].data)) == shape[0]]
        notes = []
        if len(ok) < len(items):
            notes.append(f"{len(items) - len(ok)} action(s) sent a differently shaped transaction and were ignored")
        steps = []
        for j, (key, length) in enumerate(shape):
            sub = [(a, ms[j]) for a, ms in ok]
            steps.append(_infer_command(name if j == 0 else f"{name} [packet {j + 1}]", sub, length,
                                        notes if j == 0 else [], counters.get(key, {})))
        _cross_packet_checksums(steps, [[t.data for t in ms] for _, ms in ok])
        head = steps[0]
        head.steps = steps[1:]
        if head.steps:
            head.notes.append(f"multi-packet transaction: {len(shape)} packets per action, sent in this order")
            head.confidence = round(min(c.confidence for c in steps), 2)
        commands.append(head)

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


def _cross_packet_checksums(steps: list[Command], samples: list[list[bytes]]):
    """A later packet may carry a checksum of an earlier one (e.g. 'apply' after 'write')."""
    for j in range(1, len(steps)):
        for f in steps[j].fields:
            if f.kind not in ("unknown", "lookup") or f.width != 1:
                continue
            cur = [s[j][f.offset] for s in samples]
            found = False
            for i in range(j):
                n = min(len(s[i]) for s in samples)
                for a in range(n):
                    for b in range(n, a + 1, -1):
                        for algo, (w, _) in CHECKSUMS.items():
                            if w == 1 and all(compute(algo, s[i][a:b]) == c for s, c in zip(samples, cur)):
                                f.kind, f.algo, f.covers, f.source, f.table = "checksum", algo, (a, b), i, None
                                found = True
                                break
                        if found:
                            break
                    if found:
                        break
                if found:
                    break
        unknown = sum(x.kind == "unknown" for x in steps[j].fields)
        steps[j].notes = [n for n in steps[j].notes if "lookup tables only" not in n or
                          any(x.kind == "lookup" for x in steps[j].fields)]
        steps[j].confidence = round(1.0 - unknown / max(steps[j].length, 1), 2) if len(samples) >= 3 else steps[j].confidence


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


def _bit_run(cols: list[int], nbits: int = 8) -> tuple[int, int, int] | None:
    """If varying bits form one contiguous run and outside bits are constant, return (bit_offset, bit_width, mask)."""
    if len(set(cols)) < 2:
        return None
    xor_all = 0
    for a, b in zip(cols, cols[1:]):
        xor_all |= a ^ b
    if xor_all == 0:
        return None
    lo = (xor_all & -xor_all).bit_length() - 1
    hi = xor_all.bit_length() - 1
    bw = hi - lo + 1
    if bin(xor_all).count("1") != bw:
        return None  # gaps — not a single packed field
    mask = ((1 << bw) - 1) << lo
    outside = ((1 << nbits) - 1) ^ mask
    if len({c & outside for c in cols}) != 1:
        return None
    # full-width run, or outside bits that are merely zero padding, is a normal value field.
    # A real bitfield has other constant (non-zero) bits packed beside it.
    if outside == 0 or bw == nbits:
        return None
    if all((c & outside) == 0 for c in cols):
        return None
    return lo, bw, mask


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

    # 2. values: bitfields (packed beside non-zero const bits) first, then 32/16-bit,
    #    then 8-bit, then lookups. Prefer wider bitfield spans.
    for j in range(arity):
        xs = [v[j] if j < len(v) else None for v in vals]
        if any(x is None for x in xs):
            continue
        for width in (2, 1):
            for off in range(length - width + 1):
                if not free(off, width):
                    continue
                run = _bit_run([_get(d, off, width, "le") for d in datas], 8 * width)
                if run is None:
                    continue
                bo, bw, _mask = run
                ys = [_get_bits(d, off, width, bo, bw) for d in datas]
                fit = _fit_linear(xs, ys)
                if fit:
                    bg = _get(datas[0], off, width, "le") & ~_mask
                    claim(Field(off, "bitfield", width, "le", const=bg, index=j,
                                scale=fit[0], bias=fit[1], bit_offset=bo, bit_width=bw, frames=frames))
        for width, ends in ((4, ("le", "be")), (2, ("le", "be"))):
            for off in range(length - width + 1):
                if not free(off, width):
                    continue
                for end in ends:
                    ys = [_get(d, off, width, end) for d in datas]
                    fit = _fit_linear(xs, ys)
                    if fit and all(len({d[i] for d in datas}) > 1 for i in range(off, off + width)):
                        claim(Field(off, "value", width, end, index=j, scale=fit[0], bias=fit[1], frames=frames))
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
