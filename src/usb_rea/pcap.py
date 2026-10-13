"""Pure-Python pcap/pcapng reader for USB captures.

Supported link types:
  189 LINKTYPE_USB_LINUX           (usbmon, 48-byte header)
  220 LINKTYPE_USB_LINUX_MMAPPED   (usbmon, 64-byte header)
  249 LINKTYPE_USBPCAP             (Windows USBPcap)
"""
from __future__ import annotations
import struct
from pathlib import Path
from typing import Iterator

from .model import Transfer

LINUX, LINUX_MMAPPED, USBPCAP = 189, 220, 249


def iter_packets(path: str | Path) -> Iterator[tuple[int, float, int, bytes]]:
    """Yield (frame_no, ts, linktype, raw) for each packet."""
    data = Path(path).read_bytes()
    magic = data[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d"):
        yield from _iter_pcap(data)
    elif magic == b"\x0a\x0d\x0d\x0a":
        yield from _iter_pcapng(data)
    else:
        raise ValueError(f"{path}: not a pcap/pcapng file")


def _iter_pcap(data: bytes):
    e = "<" if data[:4] in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
    nano = data[:4] in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
    linktype = struct.unpack(e + "I", data[20:24])[0]
    off, n = 24, 0
    while off + 16 <= len(data):
        sec, frac, incl, _orig = struct.unpack(e + "IIII", data[off:off + 16])
        off += 16
        n += 1
        yield n, sec + frac / (1e9 if nano else 1e6), linktype, data[off:off + incl]
        off += incl


def _iter_pcapng(data: bytes):
    off, n = 0, 0
    e = "<"
    ifaces: list[tuple[int, float]] = []
    while off + 12 <= len(data):
        btype = struct.unpack(e + "I", data[off:off + 4])[0]
        if btype == 0x0A0D0D0A:
            bom = data[off + 8:off + 12]
            e = "<" if bom == b"\x4d\x3c\x2b\x1a" else ">"
            ifaces = []
        blen = struct.unpack(e + "I", data[off + 4:off + 8])[0]
        if blen < 12:
            break
        body = data[off + 8:off + blen - 4]
        if btype == 1:  # IDB
            lt = struct.unpack(e + "H", body[:2])[0]
            res = 1e-6
            o = 8
            while o + 4 <= len(body):
                code, ln = struct.unpack(e + "HH", body[o:o + 4])
                if code == 0:
                    break
                if code == 9 and ln >= 1:
                    v = body[o + 4]
                    res = 2.0 ** -(v & 0x7F) if v & 0x80 else 10.0 ** -v
                o += 4 + ((ln + 3) & ~3)
            ifaces.append((lt, res))
        elif btype == 6:  # EPB
            iid, hi, lo, cap, _orig = struct.unpack(e + "IIIII", body[:20])
            lt, res = ifaces[iid] if iid < len(ifaces) else (LINUX_MMAPPED, 1e-6)
            n += 1
            yield n, ((hi << 32) | lo) * res, lt, body[20:20 + cap]
        elif btype == 3:  # SPB
            lt, res = ifaces[0] if ifaces else (LINUX_MMAPPED, 1e-6)
            n += 1
            yield n, 0.0, lt, body[4:]
        off += blen


_USBMON = struct.Struct("<QcBBBHccqiiII8s")  # first 48 bytes


def parse_usbmon(frame: int, ts: float, raw: bytes, hdr_len: int) -> Transfer | None:
    (_id, ev, xtype, ep, dev, bus, flag_setup, _fd, sec, usec, status,
     _length, len_cap, setup) = _USBMON.unpack(raw[:48])
    payload = raw[hdr_len:hdr_len + len_cap]
    ev = ev.decode("latin1")
    is_in = bool(ep & 0x80)
    has_setup = flag_setup == b"\x00" and xtype == 2 and ev == "S"
    if ev == "S":
        # OUT data travels on submission; control submissions carry the setup packet.
        if is_in and not has_setup:
            return None
        if xtype == 2 and has_setup and setup[0] & 0x80:
            # control IN request: keep setup, data arrives on completion
            return Transfer(frame, ts, bus, dev, ep | 0x80, xtype, setup, b"")
        return Transfer(frame, ts, bus, dev, ep & 0x7F, xtype, setup if has_setup else None, payload)
    if ev == "C" and is_in and payload:
        return Transfer(frame, ts, bus, dev, ep, xtype, None, payload)
    return None


_USBPCAP = struct.Struct("<HQIHBHHBBI")  # 27 bytes


def parse_usbpcap(frame: int, ts: float, raw: bytes) -> Transfer | None:
    hlen, _irp, _st, _fn, info, bus, dev, ep, xtype, dlen = _USBPCAP.unpack(raw[:27])
    completion = bool(info & 1)
    is_in = bool(ep & 0x80)
    payload = raw[hlen:hlen + dlen]
    setup = None
    if xtype == 2:
        stage = raw[27] if len(raw) > 27 else 0
        if stage == 0:  # setup stage: 8-byte setup packet in payload
            setup, payload = payload[:8], payload[8:]
            if completion:
                return None
            if setup and setup[0] & 0x80:
                return Transfer(frame, ts, bus, dev, ep | 0x80, xtype, setup, b"")
            return Transfer(frame, ts, bus, dev, ep & 0x7F, xtype, setup, payload)
        if stage == 1:  # data stage
            if is_in and completion and payload:
                return Transfer(frame, ts, bus, dev, ep | 0x80, xtype, None, payload)
            return None
        return None
    if not is_in and not completion and payload:
        return Transfer(frame, ts, bus, dev, ep, xtype, None, payload)
    if is_in and completion and payload:
        return Transfer(frame, ts, bus, dev, ep, xtype, None, payload)
    return None


def read_transfers(path: str | Path) -> list[Transfer]:
    out: list[Transfer] = []
    for frame, ts, lt, raw in iter_packets(path):
        t = None
        if lt == LINUX_MMAPPED and len(raw) >= 64:
            t = parse_usbmon(frame, ts, raw, 64)
        elif lt == LINUX and len(raw) >= 48:
            t = parse_usbmon(frame, ts, raw, 48)
        elif lt == USBPCAP and len(raw) >= 27:
            t = parse_usbpcap(frame, ts, raw)
        if t is not None:
            out.append(t)
    return out


def find_ids(transfers: list[Transfer]) -> dict[int, tuple[int, int]]:
    """Find (VID, PID) per device address from GET_DESCRIPTOR(DEVICE) responses."""
    ids: dict[int, tuple[int, int]] = {}
    pending: dict[int, bool] = {}
    for t in transfers:
        if t.xfer_type != 2:
            continue
        if t.setup and t.setup[1] == 6 and t.setup[3] == 1:
            pending[t.device] = True
        elif pending.get(t.device) and len(t.data) >= 12 and t.data[1] == 1:
            ids[t.device] = struct.unpack("<HH", t.data[8:12])
            pending[t.device] = False
    return ids
