"""Synthetic usbmon captures with known ground truth, for tests and demos.

Devices (VID 0x1234 / PID 0xABCD):
  lamp: bulk/HID: AA <cmd> <arg> 00 <sum8>; brightness/power/hue (8-bit)
  fan:  5A <seq> <cmd> <args> pad + CRC16/MODBUS; 16-bit BE RPM, RGB, lookup.
         Replies A5 <cmd> <seq> <arg u16 LE> <sum8>; with poll > 0 it is asked for its status and
         answers A5 40 <current RPM u16 LE> <temperature °C> 00 <sum8>; with observe=True the
         00 byte reports the current mode (00 auto until a 'mode N' command, then that mode's byte)
         and the markers note what the vendor app showed now and then ('seen rpm 1186 temp 39 mode auto')
         With handshake=True the vendor app first opens a session (see fan_handshake): hello, auth
         with the 4-byte session token from the hello reply, start (after a calibrate step when auth
         answers "needs calibration", see branch=True)
  dial: A5 <cmd> <args> <sum8>; 32-bit LE position + 4-bit level bitfield
  lcd:  screen on an AIO pump cap: brightness 12 01 00 80 <percent> padded to 64 bytes on interrupt
        EP 0x01. With image_stream=True the vendor app also streams a 240x240 JPEG video on interrupt
        EP 0x03 the whole time (see lcd_frames): 512-byte packets, header 08 <packets> 00 80 on the
        first packet of a frame and 08 <index> 00 00 on the rest, the last one zero padded; the
        device answers each frame with 08 81 + 14 zero bytes on EP 0x84
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

# states=True: the fan only takes a color in mode 3 (its custom lighting mode), so the vendor app only
# ever sends color after mode 3; fan speed works in every mode
FAN_STATE_ACTIONS = ["mode 1", "fan 800", "fan 1200", "mode 3", "color 255 0 0", "color 0 128 255",
                     "mode 2", "fan 2650", "fan 4000", "mode 3", "color 10 20 30"]

# reported=True: the mode is changed on the fan itself ('press mode N', no host traffic) or by the app
# ('mode N'); the app reads the mode from the status reply and only sends a color while it says turbo
FAN_REPORTED_ACTIONS = ["fan 800", "press mode 3", "color 255 0 0", "color 0 128 255", "press mode 1",
                        "fan 1200", "mode 2", "fan 2650", "mode 3", "color 10 20 30", "mode 1",
                        "fan 4000"]

# switch=True: the app switches to mode 3 inside every color action and back to the mode before
FAN_SWITCH_ACTIONS = ["mode 1", "fan 800", "color 255 0 0", "mode 3", "fan 1200", "mode 2",
                      "color 0 128 255", "fan 2650", "color 10 20 30", "mode 1", "color 40 50 60", "fan 4000"]


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


def fan_handshake(token: bytes, status: int = 0x01) -> list[tuple[bytes, bytes]]:
    """Fan session setup as (request, reply) pairs, requests framed like commands (5A 00 <cmd> ... CRC16):
    hello 01 -> A5 01 <4-byte session token> <sum8>; auth 02 <token> -> A5 02 <status> <sum8>;
    start 03 01 -> A5 03 01 <sum8>. Status 01 is ready; with status 02 (needs calibration) the app
    sends calibrate 04 01 -> A5 04 01 <sum8> before start."""
    from .checksums import compute

    def req(body):
        body = bytes([0x5A, 0x00]) + body
        body = body.ljust(6, b"\x00")
        return body + compute("crc16_modbus", body).to_bytes(2, "little")

    def rep(body):
        body = bytes([0xA5]) + body
        return body + bytes([sum(body) & 0xFF])
    steps = [(req(b"\x01"), rep(b"\x01" + token)), (req(b"\x02" + token), rep(bytes([0x02, status])))]
    if status == 0x02:
        steps.append((req(b"\x04\x01"), rep(b"\x04\x01")))
    return steps + [(req(b"\x03\x01"), rep(b"\x03\x01"))]


LCD_ACTIONS = ["brightness 0", "brightness 50", "brightness 100", "brightness 25", "brightness 75"]


def encode_lcd(values: list[float]) -> bytes:
    return bytes([0x12, 0x01, 0x00, 0x80, int(values[0])]).ljust(64, b"\x00")


def fake_jpeg(n: int, size: int = 240, seed: int = 0) -> bytes:
    """A JPEG-shaped image: SOI, JFIF APP0, SOF0 with the size, scan data without FF bytes, EOI.
    Not decodable, but every marker the stream detector looks at is where a real encoder puts it."""
    rnd = random.Random(seed)
    app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = b"\xff\xc0\x00\x11\x08" + size.to_bytes(2, "big") * 2 + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    sos = b"\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00"
    head = b"\xff\xd8" + app0 + sof + sos
    body = bytes(rnd.randrange(0, 255) for _ in range(max(0, n - len(head) - 2)))
    return head + body + b"\xff\xd9"


def lcd_frames(image: bytes, chunk: int = 512) -> list[bytes]:
    """Packets for one frame: header 08 <count> 00 80, then 08 <index> 00 00; last one padded."""
    room = chunk - 4
    parts = [image[i:i + room] for i in range(0, len(image), room)]
    return [(bytes([0x08, len(parts) if k == 0 else k, 0x00, 0x80 if k == 0 else 0x00]) + p).ljust(chunk, b"\x00")
            for k, p in enumerate(parts)]


def gradient(w: int, h: int, n: int = 0, bpp: int = 2, order: str = "little") -> bytes:
    """A smooth test picture (red across, green down, shifted by n) as RGB565 or RGB888 pixels."""
    out = bytearray()
    for y in range(h):
        for x in range(w):
            r, g, b = (x * 255 // max(1, w - 1) + 4 * n) & 0xFF, y * 255 // max(1, h - 1), 0x60
            if bpp == 3:
                out += bytes((r, g, b))
            else:
                out += ((r >> 3) << 11 | (g >> 2) << 5 | b >> 3).to_bytes(2, order)
    return bytes(out)


def encode_testcard(w: int, h: int, bpp: int, order: str = "rgb", endian: str = "little") -> bytes:
    """The usb-rea test card as a screen with this channel order would take it (RGB565 or RGB888)."""
    from .streams import testcard as card
    rgb = card(w, h)
    out = bytearray()
    for i in range(0, len(rgb), 3):
        r, g, b = rgb[i:i + 3] if order == "rgb" else rgb[i:i + 3][::-1]
        out += bytes((r, g, b)) if bpp == 3 else ((r >> 3) << 11 | (g >> 2) << 5 | b >> 3).to_bytes(2, endian)
    return bytes(out)


def raw_header(x: int, y: int, w: int, h: int) -> bytes:
    """Synthetic raw LCD 'draw' command: 55 AA 02 00, then x, y, width, height as u16 LE."""
    return b"\x55\xaa\x02\x00" + b"".join(v.to_bytes(2, "little") for v in (x, y, w, h))


def raw888_packets(pixels: bytes, chunk: int = 64) -> list[bytes]:
    """RGB888 frame cut into packets behind a 4-byte header: packet index and count as u16 LE."""
    room = chunk - 4
    parts = [pixels[i:i + room] for i in range(0, len(pixels), room)]
    return [k.to_bytes(2, "little") + len(parts).to_bytes(2, "little") + p for k, p in enumerate(parts)]


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
                 handshake: bool = False, reopen: bool = False, branch: bool = False,
                 states: bool = False, image_stream: bool = False, fps: float = 20.0,
                 raw: str | None = None, testcard: str | None = None,
                 endpoints: str | None = None, reported: bool = False,
                 switch: bool = False, inline: bool = False) -> tuple[Path, Path]:
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

    branch: (fan with handshake) the app opens the session again twice more, a third and two thirds of
    the way through: the first time the fan answers auth with status 02 (needs calibration) and the
    app sends a calibrate step before start, the second time it answers 01 (ready) as at first.

    states: (fan) use FAN_STATE_ACTIONS, where color is only ever sent after 'mode 3' while fan
    speed is set in modes 1 and 2, so color gets a state precondition.

    reported: (fan) use FAN_REPORTED_ACTIONS: the user changes the mode with the fan's own button
    ('press mode N' labels make no traffic and no marker) and the app only sends a color while the
    fan's status reply says turbo; it also sets mode 2 and 3 itself. Implies poll=0.25 (unless set)
    and observe=True, so the mode byte of the status reply is named.

    switch: (fan) use FAN_SWITCH_ACTIONS: every color action is sent as mode 3, the color, then the
    mode the app was in before (1 or 2), all inside the one action, each packet with its own reply.

    image_stream: (lcd) the vendor app streams a JPEG video to the screen at `fps` frames per second
    for the whole capture (frames of 1.5 to 4 KB, so 3 to 8 packets each, the first one cut off by
    the start of the capture), with an ack from the device after each frame.
    testcard: (raw streams) 'rgb' or 'bgr': frames 4 to 11 (but not the clock redraws) show the
    usb-rea test card encoded in that channel order, as when the user put it on the screen.
    raw: (lcd with image_stream) stream raw pixels instead of JPEG on bulk EP 0x02. 'rgb565': a
    160x128 screen at 10 fps, each frame a 12-byte draw command (55 AA 02 00, x, y, width, height as
    u16 LE) then RGB565 LE pixels in 512-byte packets; every 4th frame only redraws a 48x16 clock at
    (100, 8); ack 55 AA 82 00 on EP 0x82. 'rgb888': a 128x160 screen at 5 fps with no command, 64-byte
    packets each starting with the packet index and count as u16 LE (1024 packets a frame).

    inline: (rgb565) the draw command has no packet of its own: it is the first 12 bytes of the
    frame's first 512-byte packet and the pixels follow right after it (so a full frame ends with a
    12-byte packet).

    endpoints: (image streams) spread each frame over more than one host->device endpoint, as some
    screens take it. 'alternate': the frame's packets alternate between two data endpoints (JPEG on
    interrupt EP 0x03 and 0x05, raw pixels on bulk EP 0x02 and 0x04, the draw command first on the
    first one). 'blocks': the first part of the frame's packets goes to the first endpoint, the rest
    to the second (packet k of n on endpoint k * 2 // n). 'command': (rgb565) the draw command goes
    to the command endpoint (interrupt EP 0x01, next to brightness) and the pixels to bulk EP 0x02.

    device: 'lamp' (see module doc), 'fan' (counter + 16-bit BE + RGB + lookup + CRC16),
    'dial' (32-bit LE position + 4-bit brightness bitfield + sum8) or 'lcd' (brightness, image stream).
    """
    from .model import split_label, split_values
    rnd = random.Random(seed)
    if (states or reported or switch) and device != "fan":
        raise ValueError("only the synthetic fan has state-dependent commands")
    if sum((states, reported, switch)) > 1:
        raise ValueError("states, reported and switch are separate scenarios; pick one")
    if reported:
        poll, observe = poll or 0.25, True
    if image_stream and device != "lcd":
        raise ValueError("only the synthetic lcd streams images")
    if raw not in (None, "rgb565", "rgb888") or (raw and not image_stream):
        raise ValueError("raw is 'rgb565' or 'rgb888' and needs image_stream=True")
    if testcard not in (None, "rgb", "bgr") or (testcard and not raw):
        raise ValueError("testcard is 'rgb' or 'bgr' and needs a raw stream")
    if endpoints not in (None, "alternate", "blocks", "command") or (endpoints and not image_stream) \
            or (endpoints == "command" and raw != "rgb565"):
        raise ValueError("endpoints is 'alternate', 'blocks' or 'command' (rgb565 only) and needs image_stream=True")
    if inline and (raw != "rgb565" or endpoints):
        raise ValueError("inline needs raw='rgb565' on one endpoint")
    if device == "fan":
        actions = actions or (FAN_STATE_ACTIONS if states else FAN_REPORTED_ACTIONS if reported
                              else FAN_SWITCH_ACTIONS if switch else FAN_ACTIONS)
    elif device == "dial":
        actions = actions or DIAL_ACTIONS
    elif device == "lcd":
        actions = actions or LCD_ACTIONS
    actions = actions or ["brightness 0%", "brightness 25%", "brightness 50%", "brightness 75%",
                          "brightness 100%", "power off", "power on", "hue 0", "hue 120", "hue 240"]
    w = UsbmonWriter()
    t = 1_760_000_000.0
    w.control_in(t, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    if transport == "control":
        w.control_in(t + 0.01, bytes([0x81, 6, 0, 0x22, 0, 0, len(LAMP_HID_DESCRIPTOR), 0]), LAMP_HID_DESCRIPTOR)
    if (handshake or reopen or branch) and device != "fan":
        raise ValueError("only the synthetic fan does a handshake")

    def open_session(at0, token, status=0x01):
        for i, (req, rep) in enumerate(fan_handshake(token, status)):
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
    current = None            # fan: the last 'mode N' the app sent (switch=True restores it)
    for n_act, label in enumerate(actions):
        if reopen and handshake and n_act == len(actions) // 2:
            open_session(t - 0.4, random.Random(seed + 8).randbytes(4))
        if branch and handshake and n_act in (len(actions) // 3, 2 * len(actions) // 3):
            first = n_act == len(actions) // 3
            open_session(t - 0.3, random.Random(seed + (9 if first else 10)).randbytes(4), 0x02 if first else 0x01)
        start = t
        if noise:
            for _ in range(rnd.randint(1, 3)):
                w.in_(t + rnd.random() * 0.2, 0x81, b"\x00\x00\x00\x00")
        name, values = split_values(label)
        if device == "fan" and name == "press mode":
            # the user pressed the mode button on the fan itself: no host traffic and no marker,
            # only the status replies show the new mode
            modes.append((t, FAN_MODES[int(values[0])]))
            t += 0.5
            continue
        wrap = device == "fan" and switch and name == "color" and current in (1, 2)
        if device == "fan":
            seq += 1
            if wrap:   # the app switches to mode 3 just for the color, then back to the mode it was in
                msgs = [encode_fan("mode", [3], seq), encode_fan(name, values, seq + 1),
                        encode_fan("mode", [current], seq + 2)]
                seq += 2
            msg = encode_fan(name, values, seq)
            if name == "mode":
                current = int(values[0])
        elif device == "dial":
            msg = encode_dial(*split_values(label))
        elif device == "lcd":
            msg = encode_lcd(split_values(label)[1])
        else:
            name, value = split_label(label)
            msg = encode(name, value if value is not None else 0)
        if wrap:
            for k, m in enumerate(msgs):
                at = t + 0.3 + 0.03 * k
                if transport == "control":
                    w.control_out(at, bytes([0x21, 0x09, 0x00, 0x02, 0, 0, len(m), 0]), m)
                else:
                    w.out(at, 0x01, m)
                w.in_(at + 0.01, 0x81, fan_reply(m, values if m[2] == 0x20 else [0]))
                if m[2] == 0x30:
                    modes.append((at, m[3]))
        elif device == "lcd":
            w.out(t + 0.3, 0x01, msg, xtype=1)
        elif transport == "control":
            # HID SET_REPORT, output report 0
            w.control_out(t + 0.3, bytes([0x21, 0x09, 0x00, 0x02, 0, 0, len(msg), 0]), msg)
        else:
            w.out(t + 0.3, 0x01, msg)
        if wrap:
            pass
        elif device == "fan":
            w.in_(t + 0.31, 0x81, fan_reply(msg, split_values(label)[1]))
            if msg[2] == 0x10:
                targets.append((t + 0.3, int(split_values(label)[1][0])))
            elif msg[2] == 0x30:
                modes.append((t + 0.3, msg[3]))
        elif device != "lcd":
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
    if image_stream and raw:
        tf, n = 1_760_000_000.0 + 0.02, 0
        fps = 10.0 if raw == "rgb565" else 5.0
        while tf < t:
            card = testcard and 4 <= n < 12 and n % 4 != 3   # the user showed the test card for a while
            if raw == "rgb565":
                x, y, wd, ht = (100, 8, 48, 16) if n % 4 == 3 else (0, 0, 160, 128)
                pix = encode_testcard(160, 128, 2, testcard) if card else gradient(wd, ht, n)
                if inline:
                    data = raw_header(x, y, wd, ht) + pix
                    pkts = [data[i:i + 512] for i in range(0, len(data), 512)]
                else:
                    pkts = [raw_header(x, y, wd, ht)] + [pix[i:i + 512] for i in range(0, len(pix), 512)]
            else:
                pkts = raw888_packets(encode_testcard(128, 160, 3, testcard) if card else gradient(128, 160, n, bpp=3))
            eps = _stream_endpoints(endpoints, len(pkts), (0x02, 0x04), raw == "rgb565")
            xtypes = [1 if ep == 0x01 else 3 for ep in eps]
            if n == 0:   # the capture started in the middle of a frame
                pkts, eps, xtypes = pkts[3:], eps[3:], xtypes[3:]
            step = 0.0004 if raw == "rgb565" else 0.0001
            for k, pkt in enumerate(pkts):
                w.out(tf + step * k, eps[k], pkt, xtype=xtypes[k])
            if raw == "rgb565":
                w.in_(tf + step * len(pkts) + 0.001, 0x82, b"\x55\xaa\x82\x00")
            tf += 1 / fps
            n += 1
    elif image_stream:
        video = random.Random(seed + 2)
        tf, n = 1_760_000_000.0 + 0.02, 0
        while tf < t:
            pkts = lcd_frames(fake_jpeg(video.randint(1500, 4000), seed=seed * 1000 + n))
            eps = _stream_endpoints(endpoints, len(pkts), (0x03, 0x05), False)
            if n == 0:   # the capture started in the middle of a frame
                pkts, eps = pkts[2:], eps[2:]
            for k, pkt in enumerate(pkts):
                w.out(tf + 0.001 * k, eps[k], pkt, xtype=1)
            w.in_(tf + 0.001 * len(pkts) + 0.001, 0x84, b"\x08\x81" + bytes(14))
            tf += 1 / fps
            n += 1
    path = Path(path)
    w.save(path)
    mpath = path.with_suffix(path.suffix + ".actions.json")
    mpath.write_text(json.dumps(marks, indent=1))
    return path, mpath


def _stream_endpoints(how: str | None, n: int, data: tuple[int, int], command: bool) -> list[int]:
    """Endpoint of each of a frame's n packets (the first one is the draw command when `command`)."""
    if how is None:
        return [data[0]] * n
    if how == "command":
        return [0x01] + [data[0]] * (n - 1)
    head, m = ([data[0]], n - 1) if command else ([], n)
    if how == "alternate":
        return head + [data[k % 2] for k in range(m)]
    return head + [data[k * 2 // m] for k in range(m)]


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
