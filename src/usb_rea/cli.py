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

    m = sub.add_parser("mark", help="mark the action you are about to do in the vendor app")
    m.add_argument("label")
    m.add_argument("-m", "--markers", default="capture.pcapng.actions.json")

    for name, hlp in (("transfers", "list parsed transfers"), ("infer", "infer protocol (JSON)"),
                      ("report", "write evidence report (markdown)"), ("scaffold", "write pyusb driver")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("capture")
        s.add_argument("-m", "--markers")
        s.add_argument("-d", "--device", type=int)
        s.add_argument("-o", "--out")

    h = sub.add_parser("hid", help="decode a HID report descriptor (from a capture or hex)")
    h.add_argument("source", help="capture file, or descriptor hex (e.g. from /sys/class/hidraw/*/device/report_descriptor)")
    h.add_argument("--decode", metavar="HEX", help="also decode one report payload")
    h.add_argument("--type", default="Input", choices=["Input", "Output", "Feature"], help="report type for --decode")
    h.add_argument("--items", action="store_true", help="print every descriptor item")

    d = sub.add_parser("demo", help="generate a synthetic capture and run the whole pipeline")
    d.add_argument("-o", "--outdir", default="usb-rea-demo")
    d.add_argument("--device", choices=["lamp", "fan", "dial"], default="lamp")

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
        return _demo(Path(a.outdir), a.device)
    if a.cmd == "transfers":
        from .pcap import read_transfers
        for t in read_transfers(a.capture):
            print(f"{t.frame:6d} dev {t.device:3d} ep 0x{t.endpoint:02x} {t.kind:9s} "
                  f"{'OUT' if t.is_out else 'IN '} {(t.setup.hex() + ' | ') if t.setup else ''}{t.data.hex(' ')}")
        return 0

    from .pipeline import analyze, sha256
    proto = analyze(a.capture, a.markers, a.device)
    if a.cmd == "infer":
        text = json.dumps(proto.to_dict(), indent=1, default=str)
    elif a.cmd == "report":
        from .report import render
        text = render(proto, a.capture, sha256(a.capture))
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


def _demo(outdir: Path, device: str = "lamp") -> int:
    from .synth import make_capture
    from .pipeline import analyze, sha256
    from .report import render
    from .scaffold import generate
    outdir.mkdir(parents=True, exist_ok=True)
    cap, _ = make_capture(outdir / f"{device}.pcap", device=device)
    proto = analyze(cap)
    (outdir / "report.md").write_text(render(proto, str(cap), sha256(cap)))
    (outdir / f"{device}_driver.py").write_text(generate(proto))
    (outdir / "__init__.py").touch()
    print(f"captured {sum(len(c.samples) for c in proto.commands)} labelled actions, "
          f"device {proto.vid:04x}:{proto.pid:04x}\n")
    for c in proto.commands:
        print(f"{c.name:12s} {c.confidence:4.0%}  " + " | ".join(f.describe() for f in c.fields))
    print(f"\nwrote {outdir}/report.md and {outdir}/{device}_driver.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
