"""Markdown evidence report."""
from __future__ import annotations
from .infer import Protocol
from .model import XFER_NAMES


def render(proto: Protocol, capture: str = "", sha256: str = "") -> str:
    L = ["# usb-rea protocol report", ""]
    if capture:
        L.append(f"Capture: `{capture}`" + (f" (sha256 `{sha256[:16]}…`)" if sha256 else ""))
    ids = f"{proto.vid:04x}:{proto.pid:04x}" if proto.vid is not None else "unknown (no GET_DESCRIPTOR in capture)"
    L += [f"Device: `{ids}`", "",
          "Frame numbers match Wireshark's `frame.number`; open the capture and jump to them to verify each claim.", ""]
    for c in proto.commands:
        chan = f"{XFER_NAMES.get(c.xfer_type)} EP 0x{c.endpoint:02x}"
        if c.setup:
            chan += f", setup `{c.setup.hex(' ')}`"
        L += [f"## `{c.name}`", "", f"- Channel: {chan}", f"- Length: {c.length} bytes",
              f"- Confidence: {c.confidence:.0%}", "", "| Byte | Role | Encoding |", "|---|---|---|"]
        for f in c.fields:
            L.append(f"| {f.offset} | {f.kind} | `{f.describe()}` |")
        L += ["", "Evidence:", "", "| Action | Payload | Frame |", "|---|---|---|"]
        for label, hx, fr in c.samples:
            L.append(f"| {label} | `{hx}` | {fr} |")
        for n in c.notes:
            L.append(f"\n> Note: {n}")
        L.append("")
    if proto.unmatched:
        L += ["## Actions with no host→device data", ""] + [f"- {u}" for u in proto.unmatched] + [""]
    return "\n".join(L)
