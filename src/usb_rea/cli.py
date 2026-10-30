"""usb-rea command line."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from . import __version__


def _int(s):
    return int(s, 0)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="usb-rea", description="Reverse Engineer any USB gadget")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("capture", help="start/stop a usbmon/USBPcap capture")
    c.add_argument("op", choices=["start", "stop"])
    c.add_argument("-o", "--out", default="capture.pcapng")
    c.add_argument("--bus", type=int, default=0)

    m = sub.add_parser("mark", help="mark the action you are about to do in the vendor app, "
                       "or what it shows right now ('seen rpm 1180 temp 34', 'seen mode turbo')")
    m.add_argument("label")
    m.add_argument("-m", "--markers", default="capture.pcapng.actions.json")

    for name, hlp in (("transfers", "list parsed transfers"), ("infer", "infer protocol (JSON)"),
                      ("report", "write evidence report (markdown)"), ("scaffold", "write pyusb driver"),
                      ("dissector", "write a Wireshark Lua dissector")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("capture")
        s.add_argument("-m", "--markers")
        s.add_argument("-l", "--labels", help="no markers? actions in the order you clicked them, "
                       "';'-separated or a file with one per line; split at the pauses between them")
        s.add_argument("-d", "--device", type=int)
        s.add_argument("-o", "--out")
        if name == "dissector":
            s.add_argument("-n", "--name", default="usbrea", help="protocol/filter name in Wireshark")

    h = sub.add_parser("hid", help="decode a HID report descriptor (from a capture or hex)")
    h.add_argument("source", help="capture file, or descriptor hex (e.g. from /sys/class/hidraw/*/device/report_descriptor)")
    h.add_argument("--decode", metavar="HEX", help="also decode one report payload")
    h.add_argument("--type", default="Input", choices=["Input", "Output", "Feature"], help="report type for --decode")
    h.add_argument("--items", action="store_true", help="print every descriptor item")

    d = sub.add_parser("demo", help="generate a synthetic capture and run the whole pipeline")
    d.add_argument("-o", "--outdir", default="usb-rea-demo")
    d.add_argument("--device", choices=["lamp", "fan", "dial", "lcd"], default="lamp")
    d.add_argument("--raw", choices=["rgb565", "rgb888"], default=None,
                   help="lcd only: stream raw pixels instead of a JPEG video")

    r = sub.add_parser("replay", help="send one packet to a real device (requires --yes)")
    r.add_argument("vid", type=_int)
    r.add_argument("pid", type=_int)
    r.add_argument("endpoint", type=_int)
    r.add_argument("hex")
    r.add_argument("--setup", help="8-byte setup packet hex for control transfers")
    r.add_argument("--yes", action="store_true")

    sub.add_parser("mcp", help="run the MCP server (stdio)")

    a = p.parse_args(argv)
    if a.cmd is None:
        p.print_help()
        return 0
    if a.cmd == "capture":
        from . import capture
        if a.op == "start":
            print(f"capturing to {a.out} (pid {capture.start(a.out, a.bus)})")
        else:
            print("stopped" if capture.stop() else "no capture running")
        return 0
    if a.cmd == "mark":
        from .actions import append_marker
        print(json.dumps(append_marker(a.markers, a.label)))
        return 0
    if a.cmd == "replay":
        from .replay import replay
        try:
            print(replay(a.vid, a.pid, a.endpoint, bytes.fromhex(a.hex),
                         bytes.fromhex(a.setup) if a.setup else None, confirm=a.yes))
        except PermissionError as e:
            print(e, file=sys.stderr)
            return 2
        return 0
    if a.cmd == "mcp":
        from .mcp_server import run
        run()
        return 0
    if a.cmd == "hid":
        return _hid(a)
    if a.cmd == "demo":
        if a.raw and a.device != "lcd":
            p.error("--raw needs --device lcd")
        return _demo(Path(a.outdir), a.device, a.raw)
    if a.cmd == "transfers":
        from .pcap import read_transfers
        for t in read_transfers(a.capture):
            print(f"{t.frame:6d} dev {t.device:3d} ep 0x{t.endpoint:02x} {t.kind:9s} "
                  f"{'OUT' if t.is_out else 'IN '} {(t.setup.hex() + ' | ') if t.setup else ''}{t.data.hex(' ')}")
        return 0

    from .pipeline import analyze, sha256
    labels = None
    if getattr(a, "labels", None):
        from .actions import read_labels
        labels = read_labels(a.labels)
    proto = analyze(a.capture, a.markers, a.device, labels)
    if a.cmd == "infer":
        text = json.dumps(proto.to_dict(), indent=1, default=str)
    elif a.cmd == "report":
        from .report import render
        text = render(proto, a.capture, sha256(a.capture))
    elif a.cmd == "dissector":
        from .dissector import generate
        text = generate(proto, a.name)
    else:
        from .scaffold import generate
        text = generate(proto)
    if a.out:
        Path(a.out).write_text(text)
        print(f"wrote {a.out}")
    else:
        print(text)
    return 0


def _hid(a) -> int:
    from . import hid
    src = Path(a.source)
    if src.exists() and src.suffix in (".pcap", ".pcapng", ".cap"):
        from .pcap import read_transfers
        found = hid.from_transfers(read_transfers(src))
        if not found:
            print("no HID report descriptor (GET_DESCRIPTOR 0x22) in this capture; "
                  "replug the device while capturing, or pass the descriptor hex", file=sys.stderr)
            return 1
        descs = [(f"device {d}, interface {i}", raw) for (d, i), raw in sorted(found.items())]
    elif src.exists():
        raw = src.read_bytes()
        descs = [(str(src), raw)]
    else:
        descs = [("hex", bytes.fromhex(a.source.replace("0x", "").replace(",", " ")))]
    for name, raw in descs:
        desc = hid.parse(raw)
        print(f"# {name}: {len(raw)} bytes, top level {', '.join(desc.top_usages) or '?'}")
        if a.items:
            print(hid.dump(desc))
        for r in desc.reports:
            print(f"\n{r.title()}")
            for f in r.fields:
                print(f"  {f.describe()}")
        if a.decode:
            print(f"\n{a.type} {a.decode}:")
            for label, v in hid.decode(desc, a.type, bytes.fromhex(a.decode)):
                print(f"  {label} = {v}")
    return 0


def _demo(outdir: Path, device: str = "lamp", raw: str | None = None) -> int:
    from .synth import make_capture
    from .pipeline import analyze, sha256
    from .report import render
    from .scaffold import generate
    outdir.mkdir(parents=True, exist_ok=True)
    # the fan's vendor app also polls its status, so the demo shows decoded replies too
    # and the markers note what its screen showed ('seen rpm 1186 temp 39 mode auto'), which names the readings
    # it also opens a session first (hello, auth with the token from the hello reply, start) and twice more
    # later, once with a calibrate step because the fan answered auth with "needs calibration";
    # its app only sets a color in mode 3, which the driver then does first
    # the lcd's app streams a JPEG video to the screen the whole time, which is set apart from brightness
    # (with --raw it sends raw pixels instead, behind a draw command that names the screen region)
    cap, _ = make_capture(outdir / f"{device}.pcap", device=device, poll=0.5 if device == "fan" else 0.0,
                          observe=device == "fan", handshake=device == "fan", branch=device == "fan",
                          states=device == "fan", image_stream=device == "lcd", raw=raw)
    proto = analyze(cap)
    (outdir / "report.md").write_text(render(proto, str(cap), sha256(cap)))
    (outdir / f"{device}_driver.py").write_text(generate(proto))
    from .dissector import generate as dissector
    (outdir / f"{device}.lua").write_text(dissector(proto))
    (outdir / "__init__.py").touch()
    print(f"captured {sum(len(c.samples) for c in proto.commands)} labelled actions, "
          f"device {proto.vid:04x}:{proto.pid:04x}\n")
    for c in proto.commands:
        print(f"{c.name:12s} {c.confidence:4.0%}  " + " | ".join(f.describe() for f in c.fields))
    for st in proto.streams:
        from .streams import describe
        print(f"\nimage stream, kept out of the commands: {describe(st)} (driver: send_image())")
    for r in proto.states:
        print(f"  {r['command']} only sent while {r['state']} {r['value']:g} ({r['count']}x; other commands "
              f"ran in {r['state']} {', '.join(f'{v:g}' for v in r['other_values'])}): the driver sets it first")
    if proto.handshake:
        print(f"\nhandshake ({len(proto.handshake)} messages sent once when the app opens the device):")
        for st in proto.handshake:
            reuse = "".join(f", bytes {u['offset']}-{u['offset'] + u['width'] - 1} = token from step {u['step']}"
                            for u in st["uses"])
            if st.get("retries"):
                reuse += f", sent {len(st['retries']) + 1}x (the app retried)"
            if st.get("reopens"):
                reuse += f", sent again {len(st['reopens'])}x later (session reopened)"
            print(f"  {st['step']}. {st['request'] or '(control read)'} -> {st['expect'] or 'no reply'}{reuse}")
            br = st.get("branches")
            for v, c in (br["cases"].items() if br else ()):
                then = "the steps below" if c["main"] else ", ".join(
                    f"{x['request']} -> {x['expect'] or 'no reply'}" for x in c["steps"])
                print(f"     reply byte {br['offset']} = {v} ({c['count']}x"
                      f"{', most common' if v == br['default'] else ''}): {then}")
    if proto.responses:
        print("\ndevice replies:")
        for r in proto.responses:
            print(f"{r.query:12s} {r.explained}/{r.length}  " + " | ".join(f.describe() for f in r.fields))
    if proto.observations:
        hit = sum(bool(o["matched"]) for o in proto.observations)
        print(f"\n{hit} of {len(proto.observations)} 'seen' observations matched a reply byte "
              f"({', '.join(sorted({o['name'] for o in proto.observations if o['matched']}))})")
    print(f"\nwrote {outdir}/report.md, {outdir}/{device}_driver.py and the Wireshark dissector {outdir}/{device}.lua")
    return 0


if __name__ == "__main__":
    sys.exit(main())
