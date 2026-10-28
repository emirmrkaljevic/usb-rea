"""Commands the vendor app only sent while the device was in one state (set by another command).

A state-setting command is one that picks a mode: its single argument is a lookup table
(mode 1/2/3 -> 0x11/0x22/0x47) or an on/off label. Walking the actions in capture order gives the
state the device was in when each other command was sent. A command gets a precondition when
  * it was sent at least twice, every time after the setter had chosen the same value, and
  * the capture also shows the setter at another value while other commands were used,
so the user did change the state and this command still only ever appeared in one of them.
This is what the app did, not proof that the device refuses the command elsewhere.
"""
from __future__ import annotations

from .actions import commands_of
from .model import Action


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
            req = {"command": name, "state": s, "value": want, "count": len(mine),
                   "other_values": others, "setter_frames": sorted({x[2] for x in mine}),
                   "frames": [x[3] for x in mine]}
            found.append(req)
            c = by_name[name]
            c.requires = [*(c.requires or []), {k: v for k, v in req.items() if k != "command"}]
            c.notes.append(f"only sent while {s} was {want:g} ({len(mine)}x, after frame(s) "
                           f"{', '.join(map(str, req['setter_frames']))}); other commands were also used with "
                           f"{s} {', '.join(f'{v:g}' for v in others)}. The driver sets {s} {want:g} first")
    return found
