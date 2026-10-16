"""MCP server exposing usb-rea to AI agents (stdio). Requires `pip install usb-rea[mcp]`."""
from __future__ import annotations
import json
from typing import Annotated

from pydantic import Field


def build():
    try:  # mcp >= 2
        from mcp.server.mcpserver import MCPServer as FastMCP
    except ImportError:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP
    from . import capture as cap
    from .actions import append_marker, read_labels
    from .pipeline import analyze, sha256, default_markers
    from .report import render
    from .scaffold import generate
    from .replay import replay as _replay

    from . import __version__
    try:
        app = FastMCP("usb-rea", version=__version__)
    except TypeError:  # mcp 1.x FastMCP has no version argument
        app = FastMCP("usb-rea")

    def _labels(labels: str | None) -> list[str] | None:
        return read_labels(labels) if labels else None

    @app.tool()
    def capture_start(
        out: Annotated[str, Field(description="Output pcapng path (overwritten if it already exists)")] = "capture.pcapng",
        bus: Annotated[int, Field(description="usbmon bus number N for /dev/usbmonN; ignored on Windows/USBPcap. Default 0")] = 0,
    ) -> str:
        """Start a USB traffic capture into `out` (usbmon on Linux, USBPcap on Windows).

        Side effects: launches a background capture process that keeps writing until capture_stop.
        Needs elevated privileges on Linux (usbmon; typically root or a usbmon group). Does not
        touch the device itself. Pair every start with capture_stop; do not start a second capture
        while one is running. Prefer this over analysis tools when you still need live traffic.
        """
        return f"capturing to {out}, pid {cap.start(out, bus)}"

    @app.tool()
    def capture_stop() -> str:
        """Stop the running capture started by capture_start.

        Side effects: terminates the background capture process. The pcapng at the path given to
        capture_start is left on disk for report/diff_actions/scaffold_driver. Returns
        'no capture running' if nothing was started (not an error). Call this before analysing.
        """
        return "stopped" if cap.stop() else "no capture running"

    @app.tool()
    def mark_action(
        label: Annotated[str, Field(description="Action label, ideally with a value, e.g. 'brightness 50%' or 'color 255 0 0'")],
        capture: Annotated[str, Field(description="Capture path whose sidecar markers file (<capture>.actions.json) is updated")] = "capture.pcapng",
    ) -> str:
        """Record that the human is about to click this action in the vendor app.

        Side effects: appends {label, start, end} to <capture>.actions.json (creates the file).
        Call while capture_start is running, immediately before each click; end times are closed
        when the next mark arrives. Use the same label stem with different values (brightness 0%,
        50%, 100%) so inference can fit scales. For an already-finished Wireshark capture without
        markers, skip this and pass `labels` to report/diff_actions instead.
        """
        return json.dumps(append_marker(default_markers(capture), label))

    @app.tool()
    def diff_actions(
        capture: Annotated[str, Field(description="Path to a usbmon or USBPcap pcap/pcapng file")],
        markers: Annotated[str | None, Field(description="Markers JSON path; default <capture>.actions.json. Ignored when labels is set")] = None,
        device: Annotated[int | None, Field(description="USB device address to analyse; default = bus address with the most host→device payloads")] = None,
        labels: Annotated[str | None, Field(description="Marker-free mode: ';'-separated labels in click order, or a text file path (one label per line). Splits traffic at the largest pauses between host→device messages")] = None,
    ) -> str:
        """Diff packets per labelled action and infer the protocol (JSON: byte roles + evidence frames).

        Read-only analysis: does not write files or talk to hardware. Requires either markers from
        mark_action or `labels` for a finished capture with pauses between clicks. Prefer report
        when the human wants a Markdown evidence write-up; prefer scaffold_driver /
        wireshark_dissector when they want generated code.
        """
        return json.dumps(analyze(capture, markers, device, _labels(labels)).to_dict(), default=str)

    @app.tool()
    def report(
        capture: Annotated[str, Field(description="Path to a usbmon or USBPcap pcap/pcapng file")],
        markers: Annotated[str | None, Field(description="Markers JSON path; default <capture>.actions.json. Ignored when labels is set")] = None,
        device: Annotated[int | None, Field(description="USB device address to analyse; default = bus address with the most host→device payloads")] = None,
        labels: Annotated[str | None, Field(description="Marker-free mode: ';'-separated labels in click order, or a text file path (one label per line)")] = None,
    ) -> str:
        """Generate a Markdown evidence report: every claim links to frame numbers in the capture.

        Read-only: returns Markdown text (does not write a file). Same inputs as diff_actions.
        Use after capture_stop (or on an existing pcap). Choose this over diff_actions when the
        human should read the protocol; choose scaffold_driver when they need a pyusb driver.
        """
        return render(analyze(capture, markers, device, _labels(labels)), capture, sha256(capture))

    @app.tool()
    def scaffold_driver(
        capture: Annotated[str, Field(description="Path to a usbmon or USBPcap pcap/pcapng file")],
        markers: Annotated[str | None, Field(description="Markers JSON path; default <capture>.actions.json. Ignored when labels is set")] = None,
        device: Annotated[int | None, Field(description="USB device address to analyse; default = bus address with the most host→device payloads")] = None,
        labels: Annotated[str | None, Field(description="Marker-free mode: ';'-separated labels in click order, or a text file path (one label per line)")] = None,
    ) -> str:
        """Generate a standalone Python/pyusb driver source for the inferred protocol.

        Read-only analysis that returns driver source as text (does not write a file or open the
        device). Same capture/markers/labels inputs as report. Prefer wireshark_dissector when the
        goal is to keep decoding traffic in Wireshark; use replay_packet only after the human
        approved a specific packet from this driver.
        """
        return generate(analyze(capture, markers, device, _labels(labels)))

    @app.tool()
    def wireshark_dissector(
        capture: Annotated[str, Field(description="Path to a usbmon or USBPcap pcap/pcapng file")],
        markers: Annotated[str | None, Field(description="Markers JSON path; default <capture>.actions.json. Ignored when labels is set")] = None,
        device: Annotated[int | None, Field(description="USB device address to analyse; default = bus address with the most host→device payloads")] = None,
        name: Annotated[str, Field(description="Wireshark protocol/filter prefix (fields become <name>.command, <name>.checksum_ok, …)")] = "usbrea",
        labels: Annotated[str | None, Field(description="Marker-free mode: ';'-separated labels in click order, or a text file path (one label per line)")] = None,
    ) -> str:
        """Generate a Wireshark Lua dissector for the inferred protocol.

        Read-only: returns Lua source as text. Labels commands, decodes values/counters/lookups,
        and verifies checksums (usbrea.checksum_ok + expert warning). Load with
        `wireshark -X lua_script:<file>.lua capture.pcapng` or the same flag on tshark. Prefer
        scaffold_driver for a pyusb driver; prefer hid_descriptor to inspect HID report layouts.
        """
        from .dissector import generate as dissector
        return dissector(analyze(capture, markers, device, _labels(labels)), name)

    @app.tool()
    def hid_descriptor(
        source: Annotated[str, Field(description="Capture path (searches for GET_DESCRIPTOR 0x22) or raw descriptor hex / hidraw report_descriptor bytes as hex")],
        decode_hex: Annotated[str | None, Field(description="Optional report payload hex to decode with the descriptor")] = None,
        report_type: Annotated[str, Field(description="Report type for decode_hex: Input, Output, or Feature")] = "Input",
    ) -> str:
        """Decode a HID report descriptor (and optionally one report payload).

        Read-only. When `source` is a capture path, finds GET_DESCRIPTOR type 0x22 transfers
        (replug the device while capturing if none are present). When `source` is hex, parses that
        descriptor directly (e.g. from /sys/class/hidraw/*/device/report_descriptor). Use this to
        understand report IDs/sizes before or alongside report/scaffold_driver; it does not infer
        vendor protocol fields from labelled actions.
        """
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
    def replay_packet(
        vid: Annotated[int, Field(description="USB vendor id (integer, e.g. 0x1234 or 4660)")],
        pid: Annotated[int, Field(description="USB product id (integer)")],
        endpoint: Annotated[int, Field(description="Endpoint address (e.g. 0x01 OUT); for control transfers use 0 with setup_hex")],
        hex_data: Annotated[str, Field(description="Payload bytes as hex (spaces optional), e.g. 'aa 01 ff 00 00 ab'")],
        user_confirmed: Annotated[bool, Field(description="Must be true only after a human approved this exact packet; otherwise the call is refused")] = False,
        setup_hex: Annotated[str | None, Field(description="Optional 8-byte control setup packet as hex; when set, sends a control transfer instead of bulk/interrupt")] = None,
    ) -> str:
        """Send one packet to real USB hardware (destructive / irreversible on the device).

        Side effects: opens the device via libusb/pyusb and writes the packet. Refuses unless
        user_confirmed=true after the human approved this exact vid/pid/endpoint/hex_data
        (and setup_hex if any). Needs OS permission to open the device. Prefer scaffold_driver to
        generate a driver first; never set user_confirmed from an agent guess.
        """
        try:
            return _replay(vid, pid, endpoint, bytes.fromhex(hex_data),
                           bytes.fromhex(setup_hex) if setup_hex else None, confirm=user_confirmed)
        except PermissionError as e:
            return f"refused: {e}"

    return app


def run():
    build().run()
