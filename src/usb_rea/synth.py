"""Synthetic usbmon captures with known ground truth, for tests and demos.

Devices (VID 0x1234 / PID 0xABCD):
  lamp: bulk/HID: AA <cmd> <arg> 00 <sum8>; brightness/power/hue (8-bit)
  fan:  5A <seq> <cmd> <args> pad + CRC16/MODBUS; 16-bit BE RPM, RGB, lookup.
         Replies A5 <cmd> <seq> <arg u16 LE> <sum8>; with poll > 0 it is asked for its status and
         answers A5 40 <current RPM u16 LE> <temperature °C> 00 <sum8>; with observe=True the
         00 byte reports the current mode (00 auto until a 'mode N' command, then that mode's byte)
         and the markers note what the vendor app showed now and then ('seen rpm 1186 temp 39 mode auto')
         With handshake=True the vendor app first opens a session (see fan_handshake): hello, auth
         with the 4-byte session token from the hello reply, start
  dial: A5 <cmd> <args> <sum8>; 32-bit LE position + 4-bit level bitfield
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

    def _pkt(self, ts, ev, xtype, ep, data=b"", setup=None, length=None, urb=None):
        sec, usec = int(ts), int(round((ts - int(ts)) * 1e6))
        # usbmon: data flag 0 = data present, '<' = IN submit / '>' = OUT completion (nothing attached)
        flag = b"\x00" if data else (b"<" if ev == "S" else b">")
        hdr = struct.pack(
            "<QcBBBHccqiiII8siiII", urb, ev.encode(), xtype, ep, self.dev, self.bus,
            b"\x00" if setup is not None else b"-", flag,
            sec, usec, -115 if ev == "S" else 0,
            len(data) if length is None else length, len(data),
            setup or b"\x00" * 8, 0, 0, 0, 0)
        self.pkts.append((ts, hdr + data))

    def _urb(self) -> int:
        # submission and completion share one URB id, as in real usbmon (Wireshark pairs them by it)
        self._id += 1
        return 0xFFFF8880_00000000 | self._id << 8

    def out(self, ts, ep, data, xtype=3):
        u = self._urb()
        self._pkt(ts, "S", xtype, ep & 0x7F, data, urb=u)
        self._pkt(ts + 0.0001, "C", xtype, ep & 0x7F, b"", length=len(data), urb=u)

    def in_(self, ts, ep, data, xtype=1):
        u = self._urb()
        self._pkt(ts, "S", xtype, ep | 0x80, b"", length=64, urb=u)
        self._pkt(ts + 0.0002, "C", xtype, ep | 0x80, data, urb=u)

    def control_out(self, ts, setup: bytes, data: bytes):
        u = self._urb()
        self._pkt(ts, "S", 2, 0x00, data, setup=setup, urb=u)
        self._pkt(ts + 0.0001, "C", 2, 0x00, b"", length=len(data), urb=u)

    def control_in(self, ts, setup: bytes, data: bytes):
        u = self._urb()
        self._pkt(ts, "S", 2, 0x80, b"", setup=setup, length=struct.unpack("<H", setup[6:8])[0], urb=u)
        self._pkt(ts + 0.0002, "C", 2, 0x80, data, urb=u)

    def save(self, path):
        with open(path, "wb") as f:
            f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 220))
            for ts, raw in sorted(self.pkts, key=lambda p: p[0]):
                sec, usec = int(ts), int(round((ts - int(ts)) * 1e6))
                f.write(struct.pack("<IIII", sec, usec, len(raw), len(raw)) + raw)


def device_descriptor() -> bytes:
    return struct.pack("<BBHBBBBHHHBBBB", 18, 1, 0x0200, 0, 0, 0, 64, VID, PID, 0x0100, 1, 2, 0, 1)


# Vendor-defined HID interface for the lamp when it talks over SET_REPORT:
# 5-byte output report (the command) and 3-byte input report (the ACK), no report IDs.
LAMP_HID_DESCRIPTOR = bytes.fromhex(
    "06 00 ff 09 01 a1 01 15 00 26 ff 00 75 08"
    " 95 05 09 02 91 02"
    " 95 03 09 03 81 02 c0")


FAN_MODES = {1: 0x11, 2: 0x22, 3: 0x47}
FAN_MODE_NAMES = {0x00: "auto", 0x11: "silent", 0x22: "balanced", 0x47: "turbo"}   # what the vendor app shows
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


def fan_status_query() -> bytes:
    """Fan "get status": 5A 00 40, pad, CRC16/MODBUS (no sequence number)."""
    from .checksums import compute
    body = bytes([0x5A, 0x00, 0x40, 0, 0, 0])
    return body + compute("crc16_modbus", body).to_bytes(2, "little")


def fan_reply(msg: bytes, values: list[float]) -> bytes:
    """Fan ACK: A5 <cmd> <seq echo> <arg u16 LE> <sum8>; arg = set RPM for 'fan', mode byte for 'mode'."""
    cmd = msg[2]
    arg = int(values[0]) if cmd == 0x10 else msg[3] if cmd == 0x30 else 0
    body = bytes([0xA5, cmd, msg[1]]) + arg.to_bytes(2, "little")
    return body + bytes([sum(body) & 0xFF])


def fan_status(rpm: int, temp: int, mode: int = 0x00) -> bytes:
    body = bytes([0xA5, 0x40]) + rpm.to_bytes(2, "little") + bytes([temp, mode])
    return body + bytes([sum(body) & 0xFF])


def fan_handshake(token: bytes) -> list[tuple[bytes, bytes]]:
    """Fan session setup as (request, reply) pairs, requests framed like commands (5A 00 <cmd> ... CRC16):
    hello 01 -> A5 01 <4-byte session token> <sum8>; auth 02 <token> -> A5 02 01 <sum8>;
    start 03 01 -> A5 03 01 <sum8>."""
    from .checksums import compute

    def req(body):
        body = bytes([0x5A, 0x00]) + body
        body = body.ljust(6, b"\x00")
        return body + compute("crc16_modbus", body).to_bytes(2, "little")

    def rep(body):
        body = bytes([0xA5]) + body
        return body + bytes([sum(body) & 0xFF])
    return [(req(b"\x01"), rep(b"\x01" + token)), (req(b"\x02" + token), rep(b"\x02\x01")),
            (req(b"\x03\x01"), rep(b"\x03\x01"))]


DIAL_ACTIONS = [
    # values chosen so each of the 4 LE bytes varies (required to claim u32 over four u8s)
    "position 0", "position 1000", "position 50000", "position 16843009", "position 2309737967",
    "level 0", "level 3", "level 7", "level 10", "level 15",
]


def encode_dial(name: str, values: list[float]) -> bytes:
    """Fake dial: A5 <cmd> <args...> <sum8>.

    cmd 0x01 position: 32-bit LE absolute position (bytes 2..5)
    cmd 0x02 level:    brightness 0..15 in bits 0..3 of byte 2; high nibble fixed 0xB
    """
    if name == "position":
        body = bytes([0xA5, 0x01]) + int(values[0]).to_bytes(4, "little")
    else:
        # high nibble 0xB (const), low nibble = level
        body = bytes([0xA5, 0x02, 0xB0 | (int(values[0]) & 0x0F), 0x00])
    return body + bytes([sum(body) & 0xFF])


def make_capture(path, actions: list[str] | None = None, transport: str = "bulk",
                 noise: bool = True, seed: int = 0, device: str = "lamp",
                 poll: float = 0.0, poll_seq: bool = False, observe: bool = False,
                 handshake: bool = False, reopen: bool = False) -> tuple[Path, Path]:
    """Write <path> (pcap) and <path>.actions.json. Returns both paths.

    poll: if > 0, the "vendor app" also sends a status request every `poll` seconds on the
    command channel, whatever the user is doing, like most real control panels. The lamp answers
    55 10 00; the fan answers with its current RPM (follows the last 'fan N' setting, +-12 jitter)
    and a slowly drifting temperature, so tests have ground truth for decoded replies.
    poll_seq: the lamp's status request carries a sequence byte (and so a changing checksum),
    which the reply echoes.
    observe: (fan with poll) every 5th status reply is also noted as an observation marker
    'seen rpm N temp T mode M', 60 ms after the reply, as if the user read the vendor app's screen;
    the status reply then also carries the current mode byte (see FAN_MODE_NAMES), and the first
    reply after a mode change is noted as 'seen mode M'.

    reopen: (fan with handshake) halfway through, the app opens the session again (as after the
    device slept) with a new session token, between two actions.

    device: 'lamp' (see module doc), 'fan' (counter + 16-bit BE + RGB + lookup + CRC16),
    or 'dial' (32-bit LE position + 4-bit brightness bitfield + sum8).
    """
    from .model import split_label, split_values
    rnd = random.Random(seed)
    if device == "fan":
        actions = actions or FAN_ACTIONS
    elif device == "dial":
        actions = actions or DIAL_ACTIONS
    actions = actions or ["brightness 0%", "brightness 25%", "brightness 50%", "brightness 75%",
                          "brightness 100%", "power off", "power on", "hue 0", "hue 120", "hue 240"]
    w = UsbmonWriter()
    t = 1_760_000_000.0
    w.control_in(t, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    if transport == "control":
        w.control_in(t + 0.01, bytes([0x81, 6, 0, 0x22, 0, 0, len(LAMP_HID_DESCRIPTOR), 0]), LAMP_HID_DESCRIPTOR)
    if (handshake or reopen) and device != "fan":
        raise ValueError("only the synthetic fan does a handshake")

    def open_session(at0, token):
        for i, (req, rep) in enumerate(fan_handshake(token)):
            at = at0 + 0.01 * i
            if transport == "control":
                w.control_out(at, bytes([0x21, 0x09, 0x00, 0x02, 0, 0, len(req), 0]), req)
            else:
                w.out(at, 0x01, req)
            w.in_(at + 0.003, 0x81, rep)
    if handshake:
        open_session(t + 0.012, random.Random(seed + 7).randbytes(4))
    t += 0.5
    marks = []
    seq = 0x40
    targets = [(0.0, 1000)]   # fan: (time, set RPM), for the status replies
    modes = [(0.0, 0x00)]     # fan: (time, mode byte), reported in the status replies with observe
    for n_act, label in enumerate(actions):
        if reopen and handshake and n_act == len(actions) // 2:
            open_session(t - 0.4, random.Random(seed + 8).randbytes(4))
        start = t
        if noise:
            for _ in range(rnd.randint(1, 3)):
                w.in_(t + rnd.random() * 0.2, 0x81, b"\x00\x00\x00\x00")
        if device == "fan":
            seq += 1
            msg = encode_fan(*split_values(label), seq)
        elif device == "dial":
            msg = encode_dial(*split_values(label))
        else:
            name, value = split_label(label)
            msg = encode(name, value if value is not None else 0)
        if transport == "control":
            # HID SET_REPORT, output report 0
            w.control_out(t + 0.3, bytes([0x21, 0x09, 0x00, 0x02, 0, 0, len(msg), 0]), msg)
        else:
            w.out(t + 0.3, 0x01, msg)
        if device == "fan":
            w.in_(t + 0.31, 0x81, fan_reply(msg, split_values(label)[1]))
            if msg[2] == 0x10:
                targets.append((t + 0.3, int(split_values(label)[1][0])))
            elif msg[2] == 0x30:
                modes.append((t + 0.3, msg[3]))
        else:
            w.in_(t + 0.31, 0x81, bytes([0x55, msg[1], 0x00]))
        t += 1.0
        marks.append({"label": label, "start": start, "end": t - 0.01})
        t += 0.5
    if poll > 0:
        status = bytes([0xAA, 0x10, 0x00, 0x00, 0xBA])   # "get status", same shape as a command
        reply = bytes([0x55, 0x10, 0x00])
        if device == "fan":
            status = fan_status_query()
            sensor = random.Random(seed + 1)
            temp = 38
            shown = 0x00
        tp = 1_760_000_000.0 + 0.05
        n = 0
        while tp < t:
            if poll_seq and device != "fan":
                body = bytes([0xAA, 0x10, n & 0xFF, 0x00])
                status = body + bytes([sum(body) & 0xFF])
                reply = bytes([0x55, 0x10, n & 0xFF])
                n += 1
            at = tp + rnd.uniform(-0.02, 0.02) * poll
            if device == "fan":
                target = [r for ts_, r in targets if ts_ <= at][-1]
                temp = min(45, max(35, temp + sensor.choice((-1, 0, 0, 1))))
                rpm = target + sensor.randint(-12, 12)
                mode = [m for ts_, m in modes if ts_ <= at][-1] if observe else 0x00
                reply = fan_status(rpm, temp, mode)
                if observe and n % 5 == 2:
                    marks.append({"label": f"seen rpm {rpm} temp {temp} mode {FAN_MODE_NAMES[mode]}",
                                  "start": at + 0.07, "end": at + 0.07})
                elif observe and mode != shown:   # the user glances at the app after switching modes
                    marks.append({"label": f"seen mode {FAN_MODE_NAMES[mode]}", "start": at + 0.07, "end": at + 0.07})
                shown = mode
                n += 1
            if transport == "control":
                w.control_out(at, bytes([0x21, 0x09, 0x00, 0x02, 0, 0, len(status), 0]), status)
            else:
                w.out(at, 0x01, status)
            w.in_(at + 0.01, 0x81, reply)
            tp += poll
    path = Path(path)
    w.save(path)
    mpath = path.with_suffix(path.suffix + ".actions.json")
    mpath.write_text(json.dumps(marks, indent=1))
    return path, mpath


def capture_from_messages(path, messages, vid: int, pid: int, noise: bool = True, seed: int = 0):
    """Write a usbmon capture from explicit host->device messages.

    messages: list of (label, data, how) where data is bytes or a list of bytes (multi-packet) and how is ("bulk"|"interrupt", endpoint) or
    ("control", 8-byte setup). Used to replay protocols documented by other projects.
    """
    rnd = random.Random(seed)
    w = UsbmonWriter()
    t = 1_760_000_000.0
    desc = bytearray(device_descriptor())
    desc[8:12] = struct.pack("<HH", vid, pid)
    w.control_in(t, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), bytes(desc))
    t += 0.5
    marks = []
    for label, data, how in messages:
        start = t
        if noise:
            for _ in range(rnd.randint(0, 2)):
                w.in_(t + rnd.random() * 0.2, 0x81, bytes(8))
        for i, pkt in enumerate(data if isinstance(data, list) else [data]):  # list = multi-packet
            if how[0] == "control":
                w.control_out(t + 0.3 + 0.02 * i, how[1], pkt)
            else:
                w.out(t + 0.3 + 0.02 * i, how[1], pkt, xtype=1 if how[0] == "interrupt" else 3)
        t += 1.0
        marks.append({"label": label, "start": start, "end": t - 0.01})
        t += 0.5
    path = Path(path)
    w.save(path)
    mpath = path.with_suffix(path.suffix + ".actions.json")
    mpath.write_text(json.dumps(marks, indent=1))
    return path, mpath
