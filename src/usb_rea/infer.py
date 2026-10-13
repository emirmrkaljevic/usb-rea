"""Per-action diffing and protocol inference. Every claim carries frame evidence."""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict

from .actions import commands_of
from .model import Action, Transfer

CHECKSUMS = {
    "sum8": lambda b: sum(b) & 0xFF,
    "xor8": lambda b: _xor(b),
    "neg_sum8": lambda b: (-sum(b)) & 0xFF,
    "inv_sum8": lambda b: (~sum(b)) & 0xFF,
}


def _xor(b):
    x = 0
    for c in b:
        x ^= c
    return x


@dataclass
class Field:
    offset: int
    kind: str                 # const | value | checksum | command | unknown
    const: int | None = None  # for const/command
    scale: float | None = None
    bias: float | None = None
    algo: str | None = None   # checksum algorithm
    covers: tuple[int, int] | None = None  # checksum covers bytes [a, b)
    observed: list[tuple[float | None, int]] = field(default_factory=list)
    frames: list[int] = field(default_factory=list)

    def describe(self) -> str:
        if self.kind in ("const", "command"):
            return f"0x{self.const:02x}"
        if self.kind == "value":
            return f"round(value * {self.scale:g} + {self.bias:g})"
        if self.kind == "checksum":
            return f"{self.algo}(bytes[{self.covers[0]}:{self.covers[1]}])"
        return "?"


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
    samples: list[tuple[str, str, int]]   # (label, hex, frame)
    notes: list[str] = field(default_factory=list)

    def template(self) -> bytes:
        return bytes((f.const or 0) if f.kind in ("const", "command") else 0 for f in self.fields)

    def encode(self, value: float | None) -> bytes:
        b = bytearray(self.template())
        for f in self.fields:
            if f.kind == "value":
                b[f.offset] = int(round((value or 0) * f.scale + f.bias + 1e-9)) & 0xFF
        for f in self.fields:
            if f.kind == "checksum":
                b[f.offset] = CHECKSUMS[f.algo](b[f.covers[0]:f.covers[1]])
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
    if n < 2 or len(set(xs)) < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    b = my - a * mx
    # snap to "nice" numbers if they still fit
    for tol in (0, 1):
        for cand_a in (round(a), round(a, 1), round(a, 2), round(a, 3), round(a, 4)):
            for cand_b in (round(b), round(b, 2), b):
                if all(abs(round(x * cand_a + cand_b + 1e-9) - y) <= tol for x, y in zip(xs, ys)):
                    return cand_a, cand_b
    # floor-style encodings (e.g. value // 2)
    if all(abs((x * a + b) - y) <= 1 for x, y in zip(xs, ys)):
        return a, b
    return None


def _primary_message(action: Action) -> Transfer | None:
    """The command message of an action: the most 'unique' OUT message.

    OUT messages that repeat identically in every action are background chatter.
    """
    cmds = commands_of(action)
    return cmds[0] if cmds else None


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
        groups[a.name].append((a, msgs[0]))

    commands = []
    for name, items in groups.items():
        keys = Counter((t.key(), len(t.data)) for _, t in items)
        (key, length), _ = keys.most_common(1)[0]
        items_ok = [(a, t) for a, t in items if (t.key(), len(t.data)) == (key, length)]
        notes = []
        if len(items_ok) < len(items):
            notes.append(f"{len(items) - len(items_ok)} action(s) used a different endpoint/length and were ignored")
        commands.append(_infer_command(name, items_ok, length, notes))

    # command-id bytes: const positions whose value differs between commands on the same channel
    by_chan = defaultdict(list)
    for c in commands:
        by_chan[(c.endpoint, c.xfer_type, c.length)].append(c)
    for cs in by_chan.values():
        if len(cs) < 2:
            continue
        for off in range(cs[0].length):
            fs = [c.fields[off] for c in cs]
            if all(f.kind == "const" for f in fs) and len({f.const for f in fs}) == len(fs):
                for f in fs:
                    f.kind = "command"
    return Protocol(vid, pid, commands, unmatched)


def _infer_command(name, items, length, notes) -> Command:
    t0 = items[0][1]
    frames = [t.frame for _, t in items]
    fields: list[Field] = []
    datas = [t.data for _, t in items]
    values = [a.value for a, _ in items]
    for off in range(length):
        col = [d[off] for d in datas]
        f = Field(off, "unknown", observed=list(zip(values, col)), frames=frames)
        if len(set(col)) == 1:
            f.kind, f.const = "const", col[0]
        fields.append(f)
    # checksums first (they vary with value but are not a function of it alone)
    for f in fields:
        if f.kind != "unknown" or len(datas) < 2:
            continue
        for algo, fn in CHECKSUMS.items():
            for a, b in ((0, f.offset), (1, f.offset), (2, f.offset), (f.offset + 1, length)):
                # must cover >1 byte, at least one of which varies
                if b - a < 2 or all(fields[i].kind == "const" for i in range(a, b)):
                    continue
                if all(fn(d[a:b]) == d[f.offset] for d in datas):
                    f.kind, f.algo, f.covers = "checksum", algo, (a, b)
                    break
            if f.kind == "checksum":
                break
    for f in fields:
        if f.kind != "unknown":
            continue
        pts = [(v, y) for v, y in f.observed if v is not None]
        fit = _fit_linear([p[0] for p in pts], [p[1] for p in pts]) if pts else None
        if fit:
            f.kind, f.scale, f.bias = "value", float(fit[0]), float(fit[1])
    unknown = sum(f.kind == "unknown" for f in fields)
    conf = 1.0 - unknown / max(length, 1)
    if len(items) < 3:
        conf *= 0.6
        notes.append("fewer than 3 samples: record more values of this action to raise confidence")
    if unknown:
        notes.append(f"{unknown} byte(s) vary but could not be explained")
    return Command(name, t0.endpoint, t0.xfer_type, t0.setup, length, fields, round(conf, 2),
                   frames, [(a.label, t.data.hex(" "), t.frame) for a, t in items], notes)
