"""Commands the vendor app only sent while the device was in one state (set by another command).

A state-setting command is one that picks a mode: its single argument is a lookup table
(mode 1/2/3 -> 0x11/0x22/0x47) or an on/off label. Walking the actions in capture order gives the
state the device was in when each other command was sent. A command gets a precondition when
  * it was sent at least twice, every time after the setter had chosen the same value, and
  * the capture also shows the setter at another value while other commands were used,
so the user did change the state and this command still only ever appeared in one of them.
This is what the app did, not proof that the device refuses the command elsewhere.

Two more kinds of state are handled here:
  * switches inside an action (find_switches): the app sends the mode command, then the action's own
    packet(s), then (often) the mode command again to go back, all for one click. When the first
    packet of a multi-packet action decodes as a state command with the same value every time, and
    the last one (if any) as the same state command putting back the value from before the action
    (or one fixed value), the action becomes the inner packets plus a `switch` the driver replays.
  * states the device reports (find_reported): a status reply byte named as a mode or on/off flag
    ('seen mode turbo' markers). A command gets a precondition when it was sent at least twice, each
    time while the last status reply before it showed the same value, and other commands were used
    while it showed another one. A command that was followed by that reply value every time it was
    sent is how the driver switches the state; without one the driver can only check and refuse.
"""
from __future__ import annotations

from .actions import commands_of
from .checksums import compute
from .model import Action, Transfer, split_values

STALE = 5.0   # seconds: a status reply older than this does not tell the state a command was sent in


def _key(a: Action) -> str:
    from .model import split_values
    return a.name if not a.values or len(a.values) == 1 else split_values(a.label)[0]


def _is_setter(c, values: set[float]) -> bool:
    if c.steps or c.arity != 1 or len(values) < 2:
        return False
    lookup = any(f.kind == "lookup" for f in c.fields)
    return lookup or values <= {0.0, 1.0}


def find_states(actions: list[Action], commands: list) -> list[dict]:
    """Set `requires` on gated commands and return the preconditions (JSON-ready dicts)."""
    by_name = {c.name: c for c in commands}
    acts = sorted((a for a in actions if commands_of(a) and _key(a) in by_name), key=lambda a: a.start)
    values: dict[str, set[float]] = {}
    for a in acts:
        if a.values:
            values.setdefault(_key(a), set()).add(float(a.values[0]))
    setters = [n for n in by_name if _is_setter(by_name[n], values.get(n, set()))]
    found = []
    for s in setters:
        cur, frame = None, None
        seen: list[tuple[str, float | None, int | None, int]] = []   # (command, state, setter frame, frame)
        for a in acts:
            k = _key(a)
            if k == s:
                cur, frame = float(a.values[0]), commands_of(a)[0].frame
            elif k not in setters:
                seen.append((k, cur, frame, commands_of(a)[0].frame))
        for name in dict.fromkeys(k for k, *_ in seen):
            mine = [x for x in seen if x[0] == name]
            states = {x[1] for x in mine}
            if len(mine) < 2 or len(states) != 1 or None in states:
                continue
            want = states.pop()
            others = sorted({x[1] for x in seen if x[0] != name and x[1] is not None and x[1] != want})
            if not others:
                continue   # the state never changed while other commands were used: nothing to compare
            if by_name[name].switch:
                continue   # the app switches into its own state inside the action
            req = {"command": name, "state": s, "value": want, "source": "command", "count": len(mine),
                   "other_values": others, "setter_frames": sorted({x[2] for x in mine}),
                   "frames": [x[3] for x in mine]}
            found.append(req)
            c = by_name[name]
            c.requires = [*(c.requires or []), {k: v for k, v in req.items() if k != "command"}]
            c.notes.append(f"only sent while {s} was {want:g} ({len(mine)}x, after frame(s) "
                           f"{', '.join(map(str, req['setter_frames']))}); other commands were also used with "
                           f"{s} {', '.join(f'{v:g}' for v in others)}. The driver sets {s} {want:g} first")
    return found


def fmt(v) -> str:
    """A state value as text: 3 for 3.0, words as they are."""
    return f"{v:g}" if isinstance(v, float) else str(v)


def _same_channel(c, t: Transfer) -> bool:
    return (t.endpoint, t.xfer_type, t.setup[:4] if t.setup else None) == \
        (c.endpoint, c.xfer_type, c.setup[:4] if c.setup else None) and len(t.data) == c.length


def decode_setter(c, t: Transfer) -> float | None:
    """The label value a one-argument state command `c` would have sent as packet `t`, or None when
    `t` is not that command: every constant byte must match, the checksum must hold, and the argument
    must be a value that command was captured with."""
    if c.steps or c.arity != 1 or not _same_channel(c, t):
        return None
    d, got = t.data, None
    for f in c.fields:
        raw = int.from_bytes(d[f.offset:f.offset + f.width], "little" if f.endian == "le" else "big")
        if f.kind in ("const", "command"):
            if raw != f.const:
                return None
        elif f.kind == "lookup":
            back = [v for v, b in f.table.items() if b == raw]
            if len(back) != 1:
                return None
            got = float(back[0])
        elif f.kind == "value" and f.scale:
            v = (raw - f.bias) / f.scale
            known = {vs[0] for vs in (split_values(lb)[1] for lb, _, _ in c.samples) if len(vs) == 1}
            if abs(v - round(v)) > 1e-6 or round(v) not in known:
                return None
            got = float(round(v))
        elif f.kind == "checksum":
            if f.source is not None or raw != compute(f.algo, d[f.covers[0]:f.covers[1]]):
                return None
        elif f.kind != "counter":
            return None
    return got


def _rename(c, name):
    c.name = name
    for k, x in enumerate(c.steps, 2):
        x.name = f"{name} [packet {k}]"


def find_switches(actions: list[Action], commands: list) -> list[dict]:
    """Multi-packet actions that are really a state switch around the action's own packets.
    Rewrites those commands in place (inner packets only, with `switch`) and returns the switches."""
    by_name = {c.name: c for c in commands}
    acts = sorted((a for a in actions if commands_of(a) and _key(a) in by_name), key=lambda a: a.start)
    values: dict[str, set[float]] = {}
    for a in acts:
        if a.values:
            values.setdefault(_key(a), set()).add(float(a.values[0]))
    setters = [by_name[n] for n in by_name if _is_setter(by_name[n], values.get(n, set()))]
    found = []
    for c in list(commands):
        packets = [c, *c.steps]
        if len(packets) < 2 or c.name in {s.name for s in setters}:
            continue
        mine = [a for a in acts if _key(a) == c.name and len(commands_of(a)) == len(packets)
                and all(_same_channel(p, t) for p, t in zip(packets, commands_of(a)))]
        if len(mine) < 2:
            continue
        ids = {id(a): i for i, a in enumerate(mine)}
        for s in setters:
            enter = [decode_setter(s, commands_of(a)[0]) for a in mine]
            if None in enter:
                continue
            if len(set(enter)) != 1:
                c.notes.append(f"the first packet is the {s.name} command, but with different values "
                               f"({', '.join(sorted({fmt(v) for v in enter}))}): not replayed as a switch")
                break
            last = [decode_setter(s, commands_of(a)[-1]) for a in mine]
            back = None not in last and len(packets) >= 3
            inner = packets[1:-1] if back else packets[1:]
            if any(decode_setter(s, commands_of(a)[k]) is not None for a in mine for k in range(1, 1 + len(inner))):
                break   # the "action" is only more state commands
            if any(f.kind == "checksum" and f.source is not None and not 1 <= f.source <= len(inner)
                   for p in inner for f in p.fields):
                break   # a checksum over a state packet: keep the transaction as captured
            # the state each action started in: the last value its state command chose before it
            cur, before = None, {}
            for a in acts:
                k = _key(a)
                if k == s.name:
                    cur = float(a.values[0])
                elif id(a) in ids:
                    before[id(a)] = cur
                    if back:
                        cur = last[ids[id(a)]]
                    else:
                        cur = enter[0]
            restore = None
            if back:
                prev = [before[id(a)] for a in mine]
                if None not in prev and all(p == v for p, v in zip(prev, last)):
                    restore = "previous"
                elif len(set(last)) == 1:
                    restore = last[0]
                else:
                    c.notes.append(f"the last packet sets {s.name} {', '.join(fmt(v) for v in last)}, which is "
                                   "neither the value from before the action nor one fixed value: not replayed as a switch")
                    break
            # the action is the inner packets; the driver sends the state command around them
            new = inner[0]
            new.steps = inner[1:]
            for p in inner:
                for f in p.fields:
                    if f.kind == "checksum" and f.source is not None:
                        f.source -= 1
            sw = {"command": c.name, "state": s.name, "enter": enter[0], "restore": restore,
                  "count": len(mine), "packets": len(packets),
                  "enter_frames": [commands_of(a)[0].frame for a in mine],
                  "restore_frames": [commands_of(a)[-1].frame for a in mine] if back else [],
                  "restore_values": last if back else []}
            new.switch = {k: v for k, v in sw.items() if k != "command"}
            new.notes = [n for n in c.notes if not n.startswith("multi-packet")] + new.notes
            if new.steps:
                new.notes.append(f"multi-packet transaction: {len(inner)} packets per action, sent in this order")
            back_txt = ("and back to the value it had before (" + ", ".join(fmt(v) for v in last) + ")"
                        if restore == "previous" else f"and then to {s.name} {fmt(restore)}" if back
                        else "and left it there")
            new.notes.append(f"the app switched {s.name} to {fmt(enter[0])} inside this action ({len(mine)}x, "
                             f"frames {', '.join(map(str, sw['enter_frames'][:8]))}) {back_txt}; the driver does "
                             f"the same around these packets")
            new.confidence = round(min(p.confidence for p in inner), 2)
            new.samples = inner[0].samples
            _rename(new, c.name)
            commands[commands.index(c)] = new
            found.append(sw)
            break
    if found:
        from .infer import mark_command_ids
        mark_command_ids(commands)
    return found


def _reported(responses) -> list:
    """(response, field) for each status-reply byte named as a mode (word table) or an on/off flag."""
    return [(r, f) for r in responses if r.source in ("background", "control read")
            for f in r.fields if f.kind == "reading" and f.name and (f.table or f.bit_width == 1)]


def _report_value(f, data: bytes):
    raw = data[f.offset]
    if f.bit_width:
        raw = (raw >> f.bit_offset) & ((1 << f.bit_width) - 1)
    return f.table.get(raw) if f.table else float(raw)


def _replies(r, transfers: list[Transfer]) -> list[Transfer]:
    """Every IN transfer shaped like this status reply: same endpoint and length, fixed bytes and checksum hold."""
    out = []
    for t in transfers:
        if not (t.is_in and t.data and t.endpoint == r.endpoint and t.xfer_type == r.xfer_type
                and len(t.data) == r.length):
            continue
        ok = True
        for f in r.fields:
            raw = int.from_bytes(t.data[f.offset:f.offset + f.width], "little" if f.endian == "le" else "big")
            if f.kind in ("const", "echo") and f.const is not None and raw != f.const:
                ok = False
            elif f.kind == "checksum" and f.algo and raw != compute(f.algo, t.data[f.covers[0]:f.covers[1]]):
                ok = False
        if ok:
            out.append(t)
    return sorted(out, key=lambda t: t.ts)


def find_reported(actions: list[Action], commands: list, responses: list, transfers: list[Transfer]) -> list[dict]:
    """Set `requires` on commands the app only sent while a status reply showed one mode or flag value;
    return those preconditions (JSON-ready dicts, `source` "reply")."""
    from bisect import bisect_left
    by_name = {c.name: c for c in commands}
    acts = sorted((a for a in actions if commands_of(a) and _key(a) in by_name), key=lambda a: a.start)
    found = []
    for r, f in _reported(responses):
        reps = _replies(r, transfers)
        times = [t.ts for t in reps]

        def before(ts):
            i = bisect_left(times, ts) - 1
            return reps[i] if i >= 0 and ts - times[i] <= STALE else None

        def settled(a):
            """The last status reply after action `a` and before the next action (what it left the device in)."""
            ts = commands_of(a)[-1].ts
            nxt = next((commands_of(b)[0].ts for b in acts if commands_of(b)[0].ts > ts), ts + STALE)
            i = bisect_left(times, min(nxt, ts + STALE)) - 1
            return reps[i] if i >= 0 and times[i] > ts else None

        # commands that set this state: every time, the next status reply shows the value it stands for
        setters = {}
        for name, c in by_name.items():
            mine = [a for a in acts if _key(a) == name]
            if c.steps or c.arity != 1 or len(mine) < 2 or any(not a.values for a in mine):
                continue
            seen, changed = {}, False
            for a in mine:
                b, n = before(commands_of(a)[0].ts), settled(a)
                v = _report_value(f, n.data) if n else None
                if v is None or seen.setdefault(float(a.values[0]), v) != v:
                    break
                changed |= b is None or _report_value(f, b.data) != v
            else:
                if changed and len(set(seen.values())) == len(seen):
                    setters[name] = {"command": name, "map": seen, "frames": [commands_of(a)[0].frame for a in mine]}
        seen = []   # (command, reported value, reply frame, command frame)
        for a in acts:
            k = _key(a)
            if k in setters:
                continue
            t = commands_of(a)[0]
            b = before(t.ts)
            seen.append((k, _report_value(f, b.data) if b else None, b.frame if b else None, t.frame))
        for name in dict.fromkeys(k for k, *_ in seen):
            c = by_name[name]
            if c.switch or any(q.get("state") == f.name for q in c.requires or []):
                continue
            mine = [x for x in seen if x[0] == name]
            states = {x[1] for x in mine}
            if len(mine) < 2 or len(states) != 1 or None in states:
                continue
            want = states.pop()
            others = sorted({x[1] for x in seen if x[0] != name and x[1] is not None and x[1] != want}, key=str)
            if not others:
                continue
            st = next(({"command": s["command"], "value": v, "count": len(s["frames"]), "frames": s["frames"]}
                       for s in setters.values() for v, got in s["map"].items() if got == want), None)
            where = f"byte {f.offset}" + (f" bit {f.bit_offset}" if f.bit_width == 1 else
                                          f" bits {f.bit_offset}-{f.bit_offset + f.bit_width - 1}" if f.bit_width else "")
            req = {"command": name, "state": f.name, "value": want, "source": "reply", "reply": r.query,
                   "where": where, "flag": not f.table, "count": len(mine), "other_values": others,
                   "reply_frames": [x[2] for x in mine], "frames": [x[3] for x in mine], "setter": st}
            found.append(req)
            c.requires = [*(c.requires or []), {k: v for k, v in req.items() if k != "command"}]
            how = (f"switches it with {st['command']} {fmt(st['value'])} (after which the reply showed "
                   f"{fmt(want)} each time, frames {', '.join(map(str, st['frames'][:8]))}) and reads it again"
                   if st else "raises StateError when the device reports another value (no command in the "
                   "capture was seen to change it)")
            c.notes.append(f"only sent while the device reported {f.name} {fmt(want)} ({r.query} {where}, "
                           f"{len(mine)}x, replies in frames {', '.join(map(str, req['reply_frames'][:8]))}); other "
                           f"commands were also used while it reported {', '.join(map(fmt, others))}. The driver "
                           f"asks first and {how}")
    return found
