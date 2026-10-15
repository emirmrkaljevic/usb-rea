"""One-call analysis used by both the CLI and the MCP server."""
from __future__ import annotations
import hashlib
from pathlib import Path

from .actions import assign, load_markers
from .infer import infer, Protocol
from .pcap import find_ids, read_transfers


def default_markers(capture: str | Path) -> Path:
    return Path(str(capture) + ".actions.json")


def analyze(capture: str | Path, markers: str | Path | None = None, device: int | None = None,
            labels: list[str] | None = None) -> Protocol:
    ts = read_transfers(capture)
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
    if labels:
        from .actions import segment_by_gaps
        marks = segment_by_gaps(ts, labels)
    else:
        marks = load_markers(markers or default_markers(capture))
    acts = assign(ts, marks)
    proto = infer(acts, vid, pid)
    proto.hid = hid_summary(ts, proto)
    return proto


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
