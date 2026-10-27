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
    if proto.handshake:
        L += _handshake(proto)
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


def _handshake(proto: Protocol) -> list[str]:
    L = ["## Handshake (sent once, before the first action)", "",
         "Host→device messages captured before your first action marker that are not background polls "
         "and are never sent again later: what the vendor app sends when it opens the device. The "
         "generated driver replays them in this order in `open()` and checks each reply against "
         "*Expected* (`??` bytes are a session token or a checksum and are not compared; a checksum is "
         "verified instead). Each message was seen once, so a byte that changes from session to session "
         "but is never reused looks constant here: pass `check=False` if a replay is refused.", "",
         "| Step | Channel | Request | Frame | Reply | Frame | Expected |", "|---|---|---|---|---|---|---|"]
    for s in proto.handshake:
        chan = _chan(s["endpoint"], s["xfer_type"], bytes.fromhex(s["setup"]) if s["setup"] else None)
        req = "(control read)" if s["read"] else f"`{s['request']}`"
        rep = (f"`{s['reply']}`", s["reply_frame"], f"`{s['expect']}`") if s["reply"] else ("none", "-", "-")
        L.append(f"| {s['step']} | {chan} | {req} | {s['frame']} | {rep[0]} | {rep[1]} | {rep[2]} |")
    L.append("")
    for s in proto.handshake:
        if s.get("retries"):
            got = ", ".join(f"frame {r['frame']} ({'reply `' + r['reply'] + '`' if r['reply'] else 'no reply'})"
                            for r in s["retries"])
            L.append(f"- Step {s['step']} was sent {len(s['retries']) + 1} times in a row: {got}, then answered "
                     f"in frame {s['reply_frame'] if s['reply'] else '-'}. The driver resends it up to "
                     f"{len(s['retries']) + 1} times when the reply times out or differs from *Expected*.")
        if s["step"] == 1 and s.get("reopens"):
            at = ", ".join(f"frame {r['frame']} ({r['time']} s)" for r in s["reopens"])
            L.append(f"- The app sent the whole handshake again later, starting at {at}: it reopened the "
                     "session (the device woke up or reconnected). Those messages are left out of the actions; "
                     "call `open()` again when the device stops answering after sleep or a replug.")
        if s.get("branches"):
            L += _branch_lines(s)
        for u in s["uses"]:
            L.append(f"- Step {s['step']} request bytes {u['offset']}-{u['offset'] + u['width'] - 1} repeat "
                     f"bytes {u['reply_offset']}-{u['reply_offset'] + u['width'] - 1} of the reply to step "
                     f"{u['step']}: a session token or device id; the driver copies them from the live reply.")
        for t in s["tokens"]:
            for u in (u for u in t["used_by"] if "command" in u):
                pk = f" (packet {u['packet'] + 1})" if u["packet"] else ""
                L.append(f"- Command `{u['command']}`{pk} bytes {u['offset']}-{u['offset'] + t['width'] - 1} "
                         f"repeat bytes {t['reply_offset']}-{t['reply_offset'] + t['width'] - 1} of the reply "
                         f"to step {s['step']}; the driver fills them in from the live reply.")
        for e in s["echoes"]:
            L.append(f"- Step {s['step']} reply bytes {e['offset']}-{e['offset'] + e['width'] - 1} echo request "
                     f"bytes {e['query_offset']}-{e['query_offset'] + e['width'] - 1}.")
    cks = {(k, c["algo"], tuple(c["covers"])) for s in proto.handshake
           for k, c in (("request", s["request_checksum"]), ("reply", s["reply_checksum"])) if c}
    for kind in ("request", "reply"):
        algos = sorted({a for k, a, _ in cks if k == kind})
        for a in algos:
            L.append(f"- Every handshake {kind} ends in `{a}` of the bytes before it"
                     + (" (from byte 1)" if any(k == kind and x == a and c[0] for k, x, c in cks) else "")
                     + ("; the driver recomputes it." if kind == "request" else "; the driver checks it."))
    return L + [""]


def _branch_lines(s: dict) -> list[str]:
    br = s["branches"]
    off, default = br["offset"], br["default"]
    L = [f"- Step {s['step']} branches on reply byte {off}: what the app sent next depended on it."]
    for v, c in br["cases"].items():
        seen = f"seen {c['count']}x (reply frame{'s' if len(c['frames']) > 1 else ''} " \
               + ", ".join(map(str, c["frames"])) + ")"
        if c["main"]:
            then = "the steps after it in the table"
        else:
            then = ", then ".join(f"`{x['request']}` (frame {x['frame']}, reply `{x['expect'] or 'none'}`)"
                                  for x in c["steps"])
        L.append(f"  - `{v}`, {seen}: {then}")
    L.append(f"  The driver reads byte {off} of the live reply and takes the matching branch; a value the "
             f"capture never showed falls back to the most common one (`{default}`). The byte is `??` in "
             "*Expected*, since it is the answer the app checks, not a fixed byte.")
    return L


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
        L.append(f"| {o['label']} | {o['time']:g} s | {o['name']} | {_shown(o['value'])} | "
                 f"{', '.join(o['matched']) or 'no'} |")
    return L + [""]


def _evidence(f) -> list:
    """Up to 8 observations; for a mode, the first of every label is always among them."""
    if f.table is None:
        return f.observed[:8]
    first = {}
    for x in f.observed:
        first.setdefault(x[0], x)
    keep = list(first.values()) + [x for x in f.observed if x not in first.values()]
    return sorted(keep[:max(8, len(first))], key=lambda x: x[3])


def _shown(v) -> str:
    return v if isinstance(v, str) else f"{v:g}"


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
            kind = f"{'iu'[not f.signed]}{8 * f.width}" + (f.endian if f.width > 1 else "")
            if f.table is not None:
                bits = f", bits {f.bit_offset}-{f.bit_offset + f.bit_width - 1}" if f.bit_width else ""
                what = (f"(byte {f.offset}{bits}) is a mode, one raw value per label the app showed: `"
                        + ", ".join(f"0x{k:02x} = {v}" for k, v in f.table.items()) + "`")
            elif f.bit_width == 1:
                what = f"(byte {f.offset}, bit {f.bit_offset}) is on when the bit is 1"
            elif f.bit_width:
                what = f"(byte {f.offset}, bits {f.bit_offset}-{f.bit_offset + f.bit_width - 1}) is the number itself"
            else:
                what = f"({span}, {kind}) = `{formula(f.scale, f.bias)}`"
            L += ["", f"`{f.name}` {what}, "
                  f"from {len(f.observed)} observation(s) of the vendor app's display:", "",
                  "| App showed | Marker at | Raw | Reply frame |", "|---|---|---|---|"]
            L += [f"| {f.name} {('off', 'on')[int(v)] if f.bit_width == 1 else _shown(v)} | {t:g} s | "
                  f"{f'0x{raw:02x}' if f.table is not None else raw} | {fr} |"
                  for v, raw, fr, t in _evidence(f)]
        shown = r.samples[:8]
        L += ["", "Evidence" + (f" (first {len(shown)} of {r.answered}):" if r.answered > len(shown) else ":"), "",
              "| Action | Query frame | Reply | Reply frame |", "|---|---|---|---|"]
        for label, qf, hx, rf in shown:
            L.append(f"| {label or '-'} | {qf} | `{hx}` | {rf} |")
        for n in r.notes:
            L.append(f"\n> Note: {n}")
        L.append("")
    return L
