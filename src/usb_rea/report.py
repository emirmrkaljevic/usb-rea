"""Markdown evidence report."""
from __future__ import annotations
from .infer import Protocol, formula
from .model import XFER_NAMES


def render(proto: Protocol, capture: str = "", sha256: str = "") -> str:
    L = ["# usb-rea protocol report", ""]
    if capture:
        L.append(f"Capture: `{capture}`" + (f" (sha256 `{sha256[:16]}…`)" if sha256 else ""))
    ids = f"{proto.vid:04x}:{proto.pid:04x}" if proto.vid is not None else "unknown (no GET_DESCRIPTOR in capture)"
    L += [f"Device: `{ids}`", "",
          "Frame numbers match Wireshark's `frame.number`; open the capture and jump to them to verify each claim.", ""]
    hid_by_cmd = {k: v for h in proto.hid for k, v in h.get("commands", {}).items()}
    for c in [x for c0 in proto.commands for x in (c0, *c0.steps)]:
        chan = f"{XFER_NAMES.get(c.xfer_type)} EP 0x{c.endpoint:02x}"
        if c.setup:
            chan += f", setup `{c.setup.hex(' ')}`"
        L += [f"## `{c.name}`", "", f"- Channel: {chan}", f"- Length: {c.length} bytes",
              f"- Confidence: {c.confidence:.0%}"] + ([f"- HID: {hid_by_cmd[c.name]}"] if c.name in hid_by_cmd else []) + ["", "| Byte | Role | Encoding |", "|---|---|---|"]
        for f in c.fields:
            L.append(f"| {f.offset} | {f.kind} | `{f.describe()}` |")
        L += ["", "Evidence:", "", "| Action | Payload | Frame |", "|---|---|---|"]
        for label, hx, fr in c.samples:
            L.append(f"| {label} | `{hx}` | {fr} |")
        for n in c.notes:
            L.append(f"\n> Note: {n}")
        L.append("")
    for h in proto.hid:
        L += [f"## HID report descriptor, interface {h['interface']}", ""]
        if "error" in h:
            L += [f"Could not parse ({h['error']}): `{h['descriptor']}`", ""]
            continue
        L += [f"Top level: {', '.join(h['top_level']) or '?'}; {h['length']} bytes; "
              f"report IDs {'used' if h['uses_report_ids'] else 'not used'}.", ""]
        for r in h["reports"]:
            rid = f"0x{r['id']:02X}" if r["id"] else "none"
            L += [f"- {r['type']} report, id {rid}, {r['length']} bytes" + (" (vendor-defined)" if r["vendor"] else "")]
            L += [f"  - {f}" for f in r["fields"]]
        L.append("")
    if proto.background:
        L += ["## Background traffic (ignored)", "",
              "Host→device messages repeated on a steady rhythm, independent of your clicks "
              "(status polls, keep-alives; `??` marks a sequence or checksum byte that changes "
              "every time). They were left out of the analysis.", "",
              "| Channel | Payload | Count | Every | First frames |", "|---|---|---|---|---|"]
        for b in proto.background:
            chan = f"{XFER_NAMES.get(b['xfer_type'])} EP 0x{b['endpoint']:02x}"
            if b["setup"]:
                chan += f", setup `{b['setup']}`"
            L.append(f"| {chan} | `{b['payload']}` | {b['count']} | {b['period']:g} s | "
                     f"{', '.join(map(str, b['frames']))} |")
        L.append("")
    if proto.responses:
        L += _responses(proto)
    if proto.observations:
        L += _observations(proto)
    if proto.unmatched:
        L += ["## Actions with no host→device data", ""] + [f"- {u}" for u in proto.unmatched] + [""]
    return "\n".join(L)


def _observations(proto: Protocol) -> list[str]:
    obs = proto.observations
    hit = sum(bool(o["matched"]) for o in obs)
    L = ["## Observations (what the vendor app showed)", "",
         f"`seen` markers note a value the vendor app displayed; times are seconds after the first captured "
         f"packet (Wireshark's `frame.time_relative`). {hit} of {len(obs)} matched a reply byte. A reading is "
         "only named when every observation of that name near one of its replies fits the same formula; "
         "an unmatched one had no reply within 1 s, or fits no reading (or several).", "",
         "| Marker | At | Name | Value | Matched |", "|---|---|---|---|---|"]
    for o in obs:
        L.append(f"| {o['label']} | {o['time']:g} s | {o['name']} | {o['value']:g} | "
                 f"{', '.join(o['matched']) or 'no'} |")
    return L + [""]


def _chan(endpoint: int, xfer_type: int, setup: bytes | None = None) -> str:
    c = f"{XFER_NAMES.get(xfer_type)} EP 0x{endpoint:02x}"
    return c + (f", setup `{setup.hex(' ')}`" if setup else "")


def _responses(proto: Protocol) -> list[str]:
    L = ["## Device responses", "",
         "Device→host data that answers a host query: the reply to a command, to a background poll, or "
         "to a control read such as GET_REPORT. Each reply is the IN transfer that follows its query "
         "(after the typical delay for that query); `= query byte N` means the reply repeats that byte "
         "of the query, and a *reading* varies on its own: only its observed range is claimed.", ""]
    for r in proto.responses:
        what = {"command": "command", "background": "background poll", "control read": "control read"}[r.source]
        L += [f"### Reply to `{r.query}` ({what})", ""]
        if r.query_payload:
            L.append(f"- Query: {_chan(r.query_endpoint, r.query_xfer_type, r.query_setup)}, `{r.query_payload}`"
                     + (f" (packet {r.packet + 1} of the transaction)" if r.packet else ""))
        else:
            L.append(f"- Query: {_chan(r.query_endpoint, r.query_xfer_type, r.query_setup)}")
        L += [f"- Reply: {_chan(r.endpoint, r.xfer_type)}, {r.length} bytes, typically {r.latency_ms:g} ms after the query",
              f"- Answered: {r.answered} of {r.queries} queries",
              f"- Explained: {r.explained} of {r.length} bytes"
              + ("" if r.explained == r.length else " (the rest are readings)"),
              "", "| Byte | Role | Encoding |", "|---|---|---|"]
        fields = list(r.fields)
        while fields:
            f = fields.pop(0)
            run = [f]
            while f.kind == "reading" and f.width == 1 and fields and fields[0].kind == "reading" \
                    and fields[0].width == 1 and fields[0].offset == run[-1].offset + 1:
                run.append(fields.pop(0))
            if len(run) >= 4:  # a block of independent byte readings: one row
                lo, hi = min(x.limits[0] for x in run), max(x.limits[1] for x in run)
                L.append(f"| {f.offset}-{run[-1].offset} | reading | `u8 readings, seen {lo}..{hi}` |")
                continue
            for f in run:
                span = f"{f.offset}-{f.offset + f.width - 1}" if f.width > 1 else f"{f.offset}"
                L.append(f"| {span} | {f.kind} | `{f.describe()}` |")
        for f in (f for f in r.fields if f.name):
            span = f"bytes {f.offset}-{f.offset + f.width - 1}" if f.width > 1 else f"byte {f.offset}"
            what = (f"(byte {f.offset}, bit {f.bit_offset}) is on when the bit is 1" if f.bit_width == 1 else
                    f"({span}, {'u16' + f.endian if f.width == 2 else 'u8'}) = `{formula(f.scale, f.bias)}`")
            L += ["", f"`{f.name}` {what}, "
                  f"from {len(f.observed)} observation(s) of the vendor app's display:", "",
                  "| App showed | Marker at | Raw | Reply frame |", "|---|---|---|---|"]
            L += [f"| {f.name} {('off', 'on')[int(v)] if f.bit_width == 1 else f'{v:g}'} | {t:g} s | {raw} | {fr} |"
                  for v, raw, fr, t in f.observed[:8]]
        shown = r.samples[:8]
        L += ["", "Evidence" + (f" (first {len(shown)} of {r.answered}):" if r.answered > len(shown) else ":"), "",
              "| Action | Query frame | Reply | Reply frame |", "|---|---|---|---|"]
        for label, qf, hx, rf in shown:
            L.append(f"| {label or '-'} | {qf} | `{hx}` | {rf} |")
        for n in r.notes:
            L.append(f"\n> Note: {n}")
        L.append("")
    return L
