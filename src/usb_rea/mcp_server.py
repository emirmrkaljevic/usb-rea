"""MCP server exposing usb-rea to AI agents (stdio). Requires `pip install usb-rea[mcp]`."""
from __future__ import annotations
import json


def build():
    try:  # mcp >= 2
        from mcp.server.mcpserver import MCPServer as FastMCP
    except ImportError:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP
    from . import capture as cap
    from .actions import append_marker
    from .pipeline import analyze, sha256, default_markers
    from .report import render
    from .scaffold import generate
    from .replay import replay as _replay

    from . import __version__
    try:
        app = FastMCP("usb-rea", version=__version__)
    except TypeError:  # mcp 1.x FastMCP has no version argument
        app = FastMCP("usb-rea")

    @app.tool()
    def capture_start(out: str = "capture.pcapng", bus: int = 0) -> str:
        """Start capturing USB traffic (usbmon on Linux, USBPcap on Windows) into `out`."""
        return f"capturing to {out}, pid {cap.start(out, bus)}"

    @app.tool()
    def capture_stop() -> str:
        """Stop the running capture."""
        return "stopped" if cap.stop() else "no capture running"

    @app.tool()
    def mark_action(label: str, capture: str = "capture.pcapng") -> str:
        """Mark the action the user is about to perform in the vendor app, e.g. 'brightness 50%'."""
        return json.dumps(append_marker(default_markers(capture), label))

    @app.tool()
    def diff_actions(capture: str, markers: str | None = None, device: int | None = None) -> str:
        """Diff packets per action and infer the protocol. Returns JSON with byte roles and evidence frames."""
        return json.dumps(analyze(capture, markers, device).to_dict(), default=str)

    @app.tool()
    def report(capture: str, markers: str | None = None, device: int | None = None) -> str:
        """Markdown evidence report: every claim links to frame numbers in the capture."""
        return render(analyze(capture, markers, device), capture, sha256(capture))

    @app.tool()
    def scaffold_driver(capture: str, markers: str | None = None, device: int | None = None) -> str:
        """Generate a standalone Python/pyusb driver for the inferred protocol."""
        return generate(analyze(capture, markers, device))

    @app.tool()
    def wireshark_dissector(capture: str, markers: str | None = None, device: int | None = None,
                            name: str = "usbrea") -> str:
        """Generate a Wireshark Lua dissector for the inferred protocol (labels fields, decodes values,
        verifies checksums). Load it with `wireshark -X lua_script:<file>.lua capture.pcapng`."""
        from .dissector import generate as dissector
        return dissector(analyze(capture, markers, device), name)

    @app.tool()
    def hid_descriptor(source: str, decode_hex: str | None = None, report_type: str = "Input") -> str:
        """Decode a HID report descriptor: `source` is a capture path (finds GET_DESCRIPTOR 0x22) or descriptor hex.
        Optionally decode one report payload (`decode_hex`) of `report_type` Input/Output/Feature."""
        from pathlib import Path
        from . import hid
        from .pcap import read_transfers
        if Path(source).exists():
            found = hid.from_transfers(read_transfers(source))
            raws = {f"{d}:{i}": r for (d, i), r in found.items()}
        else:
            raws = {"hex": bytes.fromhex(source.replace("0x", "").replace(",", " "))}
        out = {}
        for k, raw in raws.items():
            desc = hid.parse(raw)
            out[k] = desc.to_dict()
            if decode_hex:
                out[k]["decoded"] = hid.decode(desc, report_type, bytes.fromhex(decode_hex))
        return json.dumps(out or {"error": "no HID report descriptor in capture"})

    @app.tool()
    def replay_packet(vid: int, pid: int, endpoint: int, hex_data: str, user_confirmed: bool = False,
                      setup_hex: str | None = None) -> str:
        """Send one packet to real hardware. Only set user_confirmed=True after the human approved this exact packet."""
        try:
            return _replay(vid, pid, endpoint, bytes.fromhex(hex_data),
                           bytes.fromhex(setup_hex) if setup_hex else None, confirm=user_confirmed)
        except PermissionError as e:
            return f"refused: {e}"

    return app


def run():
    build().run()
