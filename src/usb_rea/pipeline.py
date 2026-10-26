"""One-call analysis used by both the CLI and the MCP server."""
from __future__ import annotations
import hashlib
from pathlib import Path

from .actions import assign, drop_background, find_background, load_markers, observations, pattern
from .infer import infer, Protocol
from .model import is_observation
from .pcap import find_ids, read_transfers


def default_markers(capture: str | Path) -> Path:
    return Path(str(capture) + ".actions.json")


def analyze(capture: str | Path, markers: str | Path | None = None, device: int | None = None,
            labels: list[str] | None = None) -> Protocol:
    ts = read_transfers(capture)
    t0 = min((t.ts for t in ts), default=0.0)
    ids = find_ids(ts)
    if device is None:
        # the device with the most host->device data is almost always the target
        counts: dict[int, int] = {}
        for t in ts:
            if t.is_out and t.data and t.device != 0:
                counts[t.device] = counts.get(t.device, 0) + 1
        device = max(counts, key=counts.get) if counts else None
    ts = [t for t in ts if device is None or t.device == device]
    vid, pid = ids.get(device, (None, None))
    # status polls / keep-alives would otherwise split --labels captures at the wrong place
    # and land in random actions, so they are set aside before anything else
    background = find_background(ts)
    everything = ts
    ts = drop_background(ts, background)
    if labels:
        from .actions import segment_by_gaps
        # 'seen ...' labels carry no timestamp here, so there is nothing to pair them with
        marks = segment_by_gaps(ts, [lb for lb in labels if not is_observation(lb)])
    else:
        marks = load_markers(markers or default_markers(capture))
    seen = observations(marks, t0)
    from .handshake import find_reopens, reopen_ids
    # the app may send its whole handshake again mid-capture (device woke up, app reconnected):
    # that block is session setup, so it stays out of the actions
    reopens = find_reopens(everything, background, marks)
    if reopens:
        drop = reopen_ids(reopens, everything)
        ts = [t for t in ts if id(t) not in drop]
    acts = assign(ts, marks)
    proto = infer(acts, vid, pid)
    proto.hid = hid_summary(ts, proto)
    proto.background = [{"endpoint": b["key"][1], "xfer_type": b["key"][2],
                         "setup": b["key"][3] or None, "payload": pattern(b["data"], b["mask"]),
                         "count": b["count"], "period": b["period"], "frames": b["frames"][:5]}
                        for b in background]
    from .responses import analyze_responses
    proto.responses = analyze_responses(everything, proto.commands, background, seen)
    from .handshake import find_handshake
    # messages sent once before the first action; a reused session token also adds a note to the command
    proto.handshake = find_handshake(everything, background, marks, proto.commands, t0, reopens)
    proto.observations = [{k: o[k] for k in ("label", "time", "name", "value")} | {"matched": [
        f"{r.query} {_span(f)}" for r in proto.responses for f in r.fields
        if f.name == o["name"] and any(x[3] == o["time"] for x in f.observed)]} for o in seen]
    return proto


def _span(f) -> str:
    if f.bit_width == 1:
        return f"byte {f.offset} bit {f.bit_offset}"
    if f.bit_width:
        return f"byte {f.offset} bits {f.bit_offset}-{f.bit_offset + f.bit_width - 1}"
    return f"bytes {f.offset}-{f.offset + f.width - 1}" if f.width > 1 else f"byte {f.offset}"


def hid_summary(transfers, proto: Protocol) -> list[dict]:
    """Decode HID report descriptors seen in the capture and map each inferred command to its report."""
    from . import hid
    out = []
    for (_dev, iface), raw in sorted(hid.from_transfers(transfers).items()):
        try:
            desc = hid.parse(raw)
        except ValueError as e:
            out.append({"interface": iface, "descriptor": raw.hex(), "error": str(e)})
            continue
        cmds = {}
        for c in proto.commands:
            data = bytes.fromhex(c.samples[0][1].replace(" ", "")) if c.samples else b""
            rep = hid.match(desc, c.setup, c.endpoint, data)
            if rep is None:
                continue
            note = rep.title()
            if rep.length != c.length:
                note += f"; captured {c.length} bytes, descriptor says {rep.length}"
            cmds[c.name] = note
        out.append({"interface": iface, "descriptor": raw.hex(), **desc.to_dict(), "commands": cmds})
    return out


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
