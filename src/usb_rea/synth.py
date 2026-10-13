"""Synthetic usbmon captures with known ground truth, for tests and demos.

The fake "lamp" protocol (VID 0x1234 / PID 0xABCD):
  bulk OUT ep 0x01 (or HID SET_REPORT when transport='control'):
    AA <cmd> <arg> 00 <sum8 of bytes 0..3>
  cmd 0x01 brightness: arg = round(pct * 255 / 100)
  cmd 0x02 power:      arg = 1/0
  cmd 0x03 hue:        arg = hue_deg // 2   (0..179)
  device ACKs each command on interrupt IN 0x81 with: 55 <cmd> 00
  plus periodic interrupt IN polling noise: 00 00 00 00
"""
from __future__ import annotations
import json
import random
import struct
from pathlib import Path

VID, PID = 0x1234, 0xABCD
CMDS = {"brightness": 0x01, "power": 0x02, "hue": 0x03}


def encode(name: str, value: float) -> bytes:
    cmd = CMDS[name]
    if name == "brightness":
        arg = round(value * 255 / 100)
    elif name == "hue":
        arg = int(value) // 2
    else:
        arg = int(value)
    body = bytes([0xAA, cmd, arg & 0xFF, 0x00])
    return body + bytes([sum(body) & 0xFF])


class UsbmonWriter:
    def __init__(self, bus: int = 1, dev: int = 5):
        self.pkts: list[tuple[float, bytes]] = []
        self.bus, self.dev, self._id = bus, dev, 0x1000

    def _pkt(self, ts, ev, xtype, ep, data=b"", setup=None, length=None):
        self._id += 1
        sec, usec = int(ts), int(round((ts - int(ts)) * 1e6))
        hdr = struct.pack(
            "<QcBBBHccqiiII8siiII", self._id, ev.encode(), xtype, ep, self.dev, self.bus,
            b"\x00" if setup is not None else b"-", b"=" if data else b"<",
            sec, usec, -115 if ev == "S" else 0,
            len(data) if length is None else length, len(data),
            setup or b"\x00" * 8, 0, 0, 0, 0)
        self.pkts.append((ts, hdr + data))

    def out(self, ts, ep, data, xtype=3):
        self._pkt(ts, "S", xtype, ep & 0x7F, data)
        self._pkt(ts + 0.0001, "C", xtype, ep & 0x7F, b"", length=len(data))

    def in_(self, ts, ep, data, xtype=1):
        self._pkt(ts, "S", xtype, ep | 0x80, b"", length=64)
        self._pkt(ts + 0.0002, "C", xtype, ep | 0x80, data)

    def control_out(self, ts, setup: bytes, data: bytes):
        self._pkt(ts, "S", 2, 0x00, data, setup=setup)
        self._pkt(ts + 0.0001, "C", 2, 0x00, b"")

    def control_in(self, ts, setup: bytes, data: bytes):
        self._pkt(ts, "S", 2, 0x80, b"", setup=setup, length=struct.unpack("<H", setup[6:8])[0])
        self._pkt(ts + 0.0002, "C", 2, 0x80, data)

    def save(self, path):
        with open(path, "wb") as f:
            f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 220))
            for ts, raw in sorted(self.pkts, key=lambda p: p[0]):
                sec, usec = int(ts), int(round((ts - int(ts)) * 1e6))
                f.write(struct.pack("<IIII", sec, usec, len(raw), len(raw)) + raw)


def device_descriptor() -> bytes:
    return struct.pack("<BBHBBBBHHHBBBB", 18, 1, 0x0200, 0, 0, 0, 64, VID, PID, 0x0100, 1, 2, 0, 1)


FAN_MODES = {1: 0x11, 2: 0x22, 3: 0x47}
FAN_ACTIONS = ["fan 800", "fan 1200", "fan 2650", "fan 4000", "color 255 0 0", "color 0 128 255",
               "color 10 20 30", "mode 1", "mode 2", "mode 3"]


def encode_fan(name: str, values: list[float], seq: int) -> bytes:
    """Fake fan controller: 5A <seq> <cmd> <args...> pad to 6, then CRC16/MODBUS little-endian."""
    from .checksums import compute
    if name == "fan":
        args = int(values[0]).to_bytes(2, "big")
        cmd = 0x10
    elif name == "color":
        args, cmd = bytes(int(v) for v in values), 0x20
    else:
        args, cmd = bytes([FAN_MODES[int(values[0])]]), 0x30
    body = (bytes([0x5A, seq & 0xFF, cmd]) + args).ljust(6, b"\x00")
    return body + compute("crc16_modbus", body).to_bytes(2, "little")


def make_capture(path, actions: list[str] | None = None, transport: str = "bulk",
                 noise: bool = True, seed: int = 0, device: str = "lamp") -> tuple[Path, Path]:
    """Write <path> (pcap) and <path>.actions.json. Returns both paths.

    device: 'lamp' (see module doc) or 'fan' (counter + 16-bit BE value + RGB + lookup + CRC16).
    """
    from .model import split_label, split_values
    rnd = random.Random(seed)
    if device == "fan":
        actions = actions or FAN_ACTIONS
    actions = actions or ["brightness 0%", "brightness 25%", "brightness 50%", "brightness 75%",
                          "brightness 100%", "power off", "power on", "hue 0", "hue 120", "hue 240"]
    w = UsbmonWriter()
    t = 1_760_000_000.0
    w.control_in(t, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    t += 0.5
    marks = []
    seq = 0x40
    for label in actions:
        start = t
        if noise:
            for _ in range(rnd.randint(1, 3)):
                w.in_(t + rnd.random() * 0.2, 0x81, b"\x00\x00\x00\x00")
        if device == "fan":
            seq += 1
            msg = encode_fan(*split_values(label), seq)
        else:
            name, value = split_label(label)
            msg = encode(name, value if value is not None else 0)
        if transport == "control":
            # HID SET_REPORT, output report 0
            w.control_out(t + 0.3, bytes([0x21, 0x09, 0x00, 0x02, 0, 0, len(msg), 0]), msg)
        else:
            w.out(t + 0.3, 0x01, msg)
        w.in_(t + 0.31, 0x81, bytes([0x55, msg[1], 0x00]))
        t += 1.0
        marks.append({"label": label, "start": start, "end": t - 0.01})
        t += 0.5
    path = Path(path)
    w.save(path)
    mpath = path.with_suffix(path.suffix + ".actions.json")
    mpath.write_text(json.dumps(marks, indent=1))
    return path, mpath
