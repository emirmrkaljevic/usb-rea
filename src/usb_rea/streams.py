"""Continuous image streams (pictures or video for an LCD) kept apart from commands.

Some devices with a screen (AIO pump caps, keyboards and stream decks with displays) get a picture
or a whole video from the vendor app: thousands of large host->device packets on one endpoint, each
frame an encoded image cut into chunks behind a small per-packet header. Diffed as actions, that
traffic drowns the real commands (brightness, orientation) sent on another endpoint.

A stream is a host->device channel (bulk or interrupt) where at least `min_frames` packets start
an image (JPEG FF D8 FF, PNG 89 50 4E 47 0D 0A 1A 0A, GIF 'GIF8', BMP 'BM', WebP RIFF....WEBP) at the same offset. That offset
is the per-packet header length. A frame runs from its start packet until the image end marker
(JPEG FF D9, PNG IEND), the BMP bfSize or WebP RIFF chunk size byte count, the next start or a pause of a second; its packets are set aside.
Header bytes are described as constant, `nn` (the number of packets in the frame) or `ii` (the
packet's index in the frame), and a device->host message of fixed content sent about once per
frame is recorded as the per-frame ack.

Raw pixel streams (RGB565, RGB888) have no start marker and are found by size instead, see the
section further down.
"""
from __future__ import annotations
from collections import Counter

from .model import Transfer

MAGIC = {"jpeg": b"\xff\xd8\xff", "png": b"\x89PNG\r\n\x1a\n", "gif": b"GIF8", "bmp": b"BM", "webp": b"RIFF"}
END = {"jpeg": b"\xff\xd9", "png": b"IEND\xaeB`\x82"}
MAX_HEADER = 32


def _size(fmt: str, img: bytes) -> tuple[int, int] | None:
    """(width, height) from a JPEG SOF marker, the PNG IHDR, the GIF screen descriptor, BMP BITMAPINFOHEADER or WebP VP8X/VP8L/VP8."""
    if fmt == "png" and len(img) >= 24:
        return int.from_bytes(img[16:20], "big"), int.from_bytes(img[20:24], "big")
    if fmt == "gif" and len(img) >= 10:
        return int.from_bytes(img[6:8], "little"), int.from_bytes(img[8:10], "little")
    if fmt == "bmp" and len(img) >= 26:
        w = int.from_bytes(img[18:22], "little", signed=True)
        h = abs(int.from_bytes(img[22:26], "little", signed=True))
        if w > 0 and h > 0:
            return w, h
    if fmt == "webp" and len(img) >= 16 and img[8:12] == b"WEBP":
        # VP8X canvas size, else first VP8L or VP8 bitstream chunk
        i = 12
        while i + 8 <= len(img):
            tag, n = img[i:i + 4], int.from_bytes(img[i + 4:i + 8], "little")
            data, nxt = img[i + 8:i + 8 + n], i + 8 + n + (n & 1)  # RIFF pads odd chunks
            if tag == b"VP8X" and len(data) >= 10:
                w = int.from_bytes(data[4:7], "little") + 1
                h = int.from_bytes(data[7:10], "little") + 1
                if w > 0 and h > 0:
                    return w, h
            if tag == b"VP8L" and len(data) >= 5 and data[0] == 0x2F:
                bits = int.from_bytes(data[1:5], "little")
                w, h = (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
                if w > 0 and h > 0:
                    return w, h
            if tag == b"VP8 " and len(data) >= 10 and data[3:6] == b"\x9d\x01\x2a":
                w = int.from_bytes(data[6:8], "little") & 0x3FFF
                h = int.from_bytes(data[8:10], "little") & 0x3FFF
                if w > 0 and h > 0:
                    return w, h
            if n < 0 or nxt <= i:
                break
            i = nxt
    if fmt == "jpeg":
        i = 2
        while i + 9 < len(img) and img[i] == 0xFF:
            m, n = img[i + 1], int.from_bytes(img[i + 2:i + 4], "big")
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                return int.from_bytes(img[i + 7:i + 9], "big"), int.from_bytes(img[i + 5:i + 7], "big")
            i += 2 + n
    return None


def _ended(fmt: str, buf: bytes) -> int | None:
    """Length of the image in buf once its end marker arrived (JPEG: as many FF D9 as FF D8 FF, so an
    embedded thumbnail does not end the frame; BMP: the bfSize field at offset 2; WebP: RIFF chunk size + 8), else None."""
    if fmt == "bmp":
        if len(buf) < 6:
            return None
        size = int.from_bytes(buf[2:6], "little")
        if size < 14:
            return None
        return size if len(buf) >= size else None
    if fmt == "webp":
        if len(buf) < 12:
            return None
        if buf[8:12] != b"WEBP":
            return None
        size = int.from_bytes(buf[4:8], "little") + 8
        if size < 12:
            return None
        return size if len(buf) >= size else None
    end = END.get(fmt)
    if end is None:
        return None
    if fmt == "jpeg":
        depth, i = 0, 0
        while True:
            a, b = buf.find(MAGIC["jpeg"], i), buf.find(end, i)
            if b < 0:
                return None
            if 0 <= a < b:
                depth, i = depth + 1, a + 3
            else:
                depth, i = depth - 1, b + 2
                if depth <= 0:
                    return i
    k = buf.find(end)
    return None if k < 0 else k + len(end)


def _header(frames: list[list[Transfer]], h: int, first: bool) -> tuple[str, dict]:
    """Pattern of the first (or the following) packets' headers: hex, nn = packet count, ii = index.
    A count or index above 255 is looked for as a 16-bit field (little or big endian) first."""
    rows = [(f[0].data[:h], len(f), 0) for f in frames] if first else \
        [(t.data[:h], len(f), k) for f in frames for k, t in enumerate(f[1:], 1)]
    if not rows:
        return "", {}
    counts = {n for _, n, _ in rows}
    out: list[str | None] = [None] * h
    roles: dict = {}
    for j in range(h - 1):
        for order in ("little", "big"):
            if out[j] or out[j + 1]:
                break
            vals = [int.from_bytes(d[j:j + 2], order) for d, _, _ in rows]
            if max(vals) <= 255:
                continue
            if "count" not in roles and all(v == n for v, (_, n, _) in zip(vals, rows)):
                out[j] = out[j + 1] = "nn"
                roles.update(count=j, count_width=2, count_endian=order)
            elif not first and "index" not in roles and len({v - k for v, (_, _, k) in zip(vals, rows)}) == 1 \
                    and all(len({d[i] for d, _, _ in rows}) > 1 for i in (j, j + 1)):
                out[j] = out[j + 1] = "ii"
                roles.update(index=j, index_width=2, index_endian=order, index_base=vals[0] - rows[0][2])
    for j in range(h):
        if out[j]:
            continue
        vals = [d[j] for d, _, _ in rows]
        if "count" not in roles and len(counts) > 1 and all(v == n & 0xFF for v, (_, n, _) in zip(vals, rows)):
            out[j] = "nn"
            roles.update(count=j, count_width=1)
        elif not first and "index" not in roles and len({v - k for v, (_, _, k) in zip(vals, rows)}) == 1 \
                and len(set(vals)) > 1:
            out[j] = "ii"
            roles.update(index=j, index_width=1, index_base=vals[0] - rows[0][2])
        elif len(set(vals)) == 1:
            out[j] = f"{vals[0]:02x}"
        else:
            out[j] = "??"
    return " ".join(out), roles


def _channels(transfers: list[Transfer]) -> dict[tuple, list[Transfer]]:
    chans: dict[tuple, list[Transfer]] = {}
    for t in sorted(transfers, key=lambda t: t.ts):
        if t.is_out and t.data and t.xfer_type in (1, 3):
            chans.setdefault(t.key(), []).append(t)
    return chans


def find_streams(transfers: list[Transfer], min_frames: int = 3) -> list[dict]:
    """Image streams in the capture; each dict has the stream's description plus `ids` (its packets
    and acks, to leave out of everything else). A stream whose frames span several host->device
    endpoints of one device (see _multi_endpoint) replaces the per-endpoint guesses it explains."""
    chans = _channels(transfers)
    singles: dict[tuple, dict] = {}
    for key, pkts in chans.items():
        s = _encoded_stream(transfers, key, pkts, min_frames) or _raw_stream(transfers, key, pkts, min_frames)
        if s:
            singles[key] = s
    found = list(singles.values())
    for m, keys in _multi_endpoint(transfers, chans, singles, min_frames):
        gone = [singles[k] for k in keys if k in singles]
        at = min((found.index(g) for g in gone), default=len(found))
        found = [s for s in found if all(s is not g for g in gone)]
        found.insert(min(at, len(found)), m)
    for s in found:
        _finish(s)
    return found


def _encoded_stream(transfers: list[Transfer], key: tuple, pkts: list[Transfer], min_frames: int) -> dict | None:
    """A JPEG/PNG/GIF/BMP/WebP stream on these packets (one channel, or several merged by time), or None."""
    best = None
    for fmt, magic in MAGIC.items():
        offs = Counter()
        for t in pkts:
            o = t.data.find(magic)
            if 0 <= o <= MAX_HEADER and (fmt != "webp" or (o + 12 <= len(t.data) and t.data[o + 8:o + 12] == b"WEBP")):
                offs[o] += 1
        if offs:
            h, n = offs.most_common(1)[0]
            if n >= min_frames and (best is None or n > best[2]):
                best = (fmt, h, n)
    if best is None:
        return None
    fmt, h, _ = best
    magic = MAGIC[fmt]
    starts = [i for i, t in enumerate(pkts) if t.data[h:h + len(magic)] == magic and (
        fmt != "webp" or (h + 12 <= len(t.data) and t.data[h + 8:h + 12] == b"WEBP"))]
    frames, sizes, dims = [], [], Counter()
    for si, s in enumerate(starts):
        stop = starts[si + 1] if si + 1 < len(starts) else len(pkts)
        members, buf = [pkts[s]], pkts[s].data[h:]
        n_img = _ended(fmt, buf)
        k = s + 1
        while n_img is None and k < stop and pkts[k].ts - pkts[k - 1].ts < 1.0:
            members.append(pkts[k])
            buf += pkts[k].data[h:]
            n_img = _ended(fmt, buf)
            k += 1
        frames.append(members)
        if n_img is not None:
            sizes.append(n_img)
        if len(dims) < 50:
            d = _size(fmt, buf)
            if d:
                dims[d] += 1
    ids = {id(t) for f in frames for t in f}
    lens = Counter(len(t.data) for f in frames for t in f)
    chunk = lens.most_common(1)[0][0]
    padded = lens[chunk] >= 0.95 * len(ids)
    first, froles = _header(frames, h, True)
    nxt, nroles = _header([f for f in frames if len(f) > 1], h, False)
    # chunks of a frame cut off by the start or a pause of the capture: same size, same fixed
    # header bytes as the packets that follow a frame's first one
    fixed = [(j, int(b, 16)) for j, b in enumerate(nxt.split()) if b not in ("nn", "ii", "??")]
    orphans = [t for t in pkts if id(t) not in ids and len(t.data) == chunk and h and nxt
               and all(t.data[j] == v for j, v in fixed)]
    ids |= {id(t) for t in orphans}
    span = frames[-1][0].ts - frames[0][0].ts
    s = {"endpoint": key[1], "xfer_type": key[2], "format": fmt, "frames": len(frames),
         "packets": len(ids), "partial": len(orphans), "chunk": chunk, "padded": padded,
         "header_len": h, "first_header": first, "next_header": nxt,
         "count_offset": froles.get("count", nroles.get("count")),
         "index_offset": nroles.get("index"), "index_base": nroles.get("index_base"),
         "count_in_next": "count" in nroles,
         "packets_per_frame": [min(map(len, frames)), max(map(len, frames))],
         "image_bytes": [min(sizes), max(sizes)] if sizes else None,
         "size": list(dims.most_common(1)[0][0]) if dims else None,
         "fps": round((len(frames) - 1) / span, 1) if span > 0 else None,
         "first_frames": [f[0].frame for f in frames[:5]], "ack": None}
    s.update({k: froles.get(k, nroles.get(k)) for k in ("count_width", "count_endian")})
    s.update({k: nroles.get(k) for k in ("index_width", "index_endian")})
    s.update(raw=False, header_packet=None, header_inline=False, region=None, length_field=None, byteorder=None,
             size_alternatives=[], frame_bytes=None, regions=0, channel_order=None, channel_evidence=None)
    _add_ack(s, transfers, key[0], frames, ids)
    s["ids"] = ids
    s.update(_frames=frames, _heads=[], _complete=len(sizes))
    return s


# ---- streams over several endpoints ----
#
# Some screens take a frame over more than one host->device endpoint: the packets alternate
# between two bulk endpoints, the first part of the frame goes to one endpoint and the rest to
# another, or a draw command goes to the command endpoint and the pixels to a data endpoint. Seen
# one endpoint at a time such a stream is missed or cut into broken frames. So for every device
# with more than one host->device channel the channels are also merged by time and searched again.
# A merged stream is kept only when most of its frames really use more than one endpoint (so two
# screens on two endpoints stay two streams) and it explains as many whole frames (give or take a
# frame cut by each end of the capture) and at least as many packets as the streams found on its
# endpoints one by one.

MAX_MERGE = 4   # data channels of one device tried together


def _uses_several(s: dict) -> bool:
    frames, heads = s["_frames"], s["_heads"]
    if not frames:
        return False
    spans = sum(1 for f in frames if len({t.endpoint for t in f}) > 1)
    data_eps = {t.endpoint for f in frames for t in f}
    cmd = sum(1 for h in heads if h.endpoint not in data_eps)
    return spans >= 0.5 * len(frames) or cmd >= 0.5 * len(frames)


def _multi_endpoint(transfers: list[Transfer], chans: dict, singles: dict, min_frames: int) -> list[tuple[dict, tuple]]:
    """Streams whose frames span several endpoints, each with the channel keys it replaces."""
    from itertools import combinations
    by_dev: dict[int, list[tuple]] = {}
    for key in chans:
        by_dev.setdefault(key[0], []).append(key)
    out = []
    for dev, keys in by_dev.items():
        if len(keys) < 2:
            continue
        data = [k for k in keys if sum(len(t.data) > MAX_HEADER_PKT for t in chans[k]) >= 0.5 * len(chans[k])]
        data = sorted(data, key=lambda k: -len(chans[k]))[:MAX_MERGE]
        cmd = tuple(k for k in keys if k not in data)
        # the packet size each data channel mostly uses; a frame is only looked for over channels
        # that share it (a command channel of 64-byte reports next to 1024-byte image chunks is not one)
        chunk = {k: Counter(len(t.data) for t in chans[k]).most_common(1)[0][0] for k in data}
        cands = []
        for n in range(len(data), 0, -1):
            for sub in combinations(data, n):
                encoded = any(not singles[k]["raw"] for k in sub if k in singles)
                tries = []
                if n >= 2 and len({chunk[k] for k in sub}) == 1:
                    tries.append((sub, True))
                if cmd and not encoded:
                    tries.append((sub + cmd, False))   # a draw command on a command endpoint
                for group, allow_encoded in tries:
                    pkts = sorted((t for k in group for t in chans[k]), key=lambda t: (t.ts, t.frame))
                    key = group[0]
                    m = (_encoded_stream(transfers, key, pkts, min_frames) if allow_encoded else None)
                    if m is None and not encoded:
                        m = _raw_stream(transfers, key, pkts, min_frames)
                    if m is None or not _uses_several(m):
                        continue
                    mine = [singles[k] for k in group if k in singles]
                    best = max((s["_complete"] for s in mine), default=0)
                    covered = sum(s["packets"] for s in mine)
                    # a tie means the endpoints alone each looked like a smaller screen in step
                    # with the other: one frame over both is the simpler story. One endpoint alone
                    # can see one more whole frame at each end, where the capture cut a frame.
                    if m["_complete"] + 2 >= best and m["packets"] >= covered:
                        cands.append(((m["_complete"], m["packets"]), m, group))
        taken: set = set()
        for _, m, group in sorted(cands, key=lambda c: c[0], reverse=True):
            if taken.isdisjoint(group):
                taken |= set(group)
                out.append((m, group))
    return out


def _finish(s: dict) -> None:
    """Which endpoints carry the stream's frames, in what layout, and where its draw command goes."""
    frames, heads = s.pop("_frames"), s.pop("_heads")
    s.pop("_complete", None)
    order: list[int] = []
    for f in sorted(frames, key=len, reverse=True)[:1] + frames:
        for t in f:
            if t.endpoint not in order:
                order.append(t.endpoint)
    n = len(order)
    layout = None
    if n > 1:
        multi = [f for f in frames if len(f) >= n]
        if all(t.endpoint == order[k % n] for f in multi for k, t in enumerate(f)):
            layout = "alternate"
        elif all(t.endpoint == order[k * n // len(f)] for f in multi for k, t in enumerate(f)):
            layout = "blocks"
        else:
            layout = "mixed"
        types = {t.endpoint: t.xfer_type for f in frames for t in f}
        s["endpoint"], s["xfer_type"] = order[0], types[order[0]]
    head_eps = Counter(h.endpoint for h in heads)
    head_ep = head_eps.most_common(1)[0][0] if head_eps else None
    s["endpoints"] = order or [s["endpoint"]]
    s["endpoint_layout"] = layout
    s["header_endpoint"] = head_ep if head_ep is not None and head_ep not in order else None


def _add_ack(s: dict, transfers: list[Transfer], device: int, frames: list, ids: set) -> None:
    """A fixed device->host message sent about once per frame on the same device is the frame ack.

    Counted per frame, not over the whole capture: a message counts for a frame when it arrives
    between the frame's start and the next frame (at most a second after the frame's last packet).
    It is the ack when at least half the frames get one and most of those get exactly one, so a
    burst of copies while no frames go out (a paused or trimmed stream) does not hide it.
    """
    acks: dict[tuple, list[Transfer]] = {}
    for t in transfers:
        if t.is_in and t.data and t.device == device and t.xfer_type in (1, 3):
            acks.setdefault((t.endpoint, t.data), []).append(t)
    starts = [f[0].ts for f in frames]
    windows = [(f[0].ts, min(nxt, f[-1].ts + 1.0)) for f, nxt in zip(frames, starts[1:] + [float("inf")])]
    best = None
    for (ep, d), g in acks.items():
        per = [sum(a <= t.ts < b for t in g) for a, b in windows]
        hit = sum(1 for n in per if n)
        single = per.count(1)
        if hit >= 0.5 * len(frames) and single >= 2 / 3 * hit and (best is None or hit > best[0]):
            best = (hit, ep, d, g)
    if best:
        hit, ep, d, g = best
        s["ack"] = {"endpoint": ep, "payload": d.hex(" "), "count": len(g), "frames_acked": hit,
                    "frames": [t.frame for t in g[:5]]}
        ids |= {id(t) for t in g}


def drop_streams(transfers: list[Transfer], streams: list[dict]) -> list[Transfer]:
    ids = set().union(*(s["ids"] for s in streams)) if streams else set()
    return [t for t in transfers if id(t) not in ids]


def describe(s: dict) -> str:
    """One line: 'jpeg stream on interrupt EP 0x03: 8670 frames, ...'."""
    from .model import XFER_NAMES
    size = f" {s['size'][0]}x{s['size'][1]}," if s["size"] else ""
    ack = f"; ack {s['ack']['payload']} on EP 0x{s['ack']['endpoint']:02x}" if s["ack"] else ""
    hdr = f", header `{s['first_header']}` then `{s['next_header']}`" if s["header_len"] else ""
    if s.get("header_packet"):
        hdr += f", each frame after a command `{s['header_packet']}`"
    part = f" ({s['regions']} redraw part of the screen)" if s.get("regions") else ""
    order = f" {s['byteorder']}-endian" if s.get("byteorder") else ""
    if s.get("channel_order"):
        order += f" {s['channel_order'].upper()}"
    kind = f"raw {s['format']}{order}" if s.get("raw") else s["format"]
    return (f"{kind} stream on {XFER_NAMES.get(s['xfer_type'])} {endpoints(s)}:{size} "
            f"{s['frames']} frames{part} in {s['packets']} packets of {s['chunk']} bytes{hdr}{ack}")


LAYOUTS = {"alternate": "packets alternate between them", "blocks": "each frame's first part on the first one",
           "mixed": "no fixed order"}


def endpoints(s: dict) -> str:
    """'EP 0x02', or 'EP 0x02 + 0x04 (packets alternate between them), command on EP 0x01'."""
    eps = s.get("endpoints") or [s["endpoint"]]
    out = "EP " + " + ".join(f"0x{e:02x}" for e in eps)
    if s.get("endpoint_layout"):
        out += f" ({LAYOUTS[s['endpoint_layout']]})"
    if s.get("header_endpoint") is not None:
        out += f", command on EP 0x{s['header_endpoint']:02x}"
    return out


# ---- raw pixel streams (no image file format) ----
#
# Many cheap case and AIO screens take plain pixels: RGB565 (2 bytes a pixel) or RGB888 (3 bytes),
# usually behind a small command that says where on the screen they go. Nothing in the bytes says
# "image", so a raw stream is found by size: on one host->device channel, runs of large packets
# (all but the last the same length, no pause between them) whose payload is exactly
# width x height x bytes per pixel for a common screen size, or exactly the region a short packet
# sent just before the run describes (x, y, width, height or x0, y0, x1, y1 as 16-bit fields, or
# four 10-bit fields packed into 5 bytes). At least `min_frames` such frames make a stream.

SCREENS = [(128, 128), (128, 160), (160, 128), (160, 80), (80, 160), (240, 135), (135, 240), (240, 240),
           (240, 280), (280, 240), (240, 320), (320, 240), (170, 320), (320, 170), (172, 320), (320, 172),
           (320, 320), (360, 360), (320, 480), (480, 320), (480, 272), (272, 480), (412, 412), (466, 466),
           (480, 480), (480, 800), (800, 480), (480, 854), (854, 480), (640, 480), (480, 640), (800, 600),
           (1024, 600), (600, 1024), (1280, 480), (480, 1280), (1920, 480), (480, 1920)]
RAW = {"rgb565": 2, "rgb888": 3}
SIZES: dict[int, list[tuple[str, int, int]]] = {}
for _fmt, _bpp in RAW.items():
    for _w, _h in SCREENS:
        SIZES.setdefault(_w * _h * _bpp, []).append((_fmt, _w, _h))
GAP = 0.03          # longest pause between two packets of one raw frame, in seconds
MAX_HEADER_PKT = 32  # a packet this short right before a run is the run's header (command) packet
REGION_TOKENS = {"xywh": ("xx", "yy", "ww", "hh"), "box": ("xx", "yy", "ex", "ey"), "wh": ("ww", "hh")}


def _region(layout: str, hdr: bytes, off: int, order: str) -> tuple[int, int, int, int] | None:
    """(x, y, width, height) a header packet gives in this layout, or None if it does not fit."""
    if layout == "box10":   # four 10-bit fields x, y, end x, end y packed into 5 bytes
        if len(hdr) < off + 5:
            return None
        v = int.from_bytes(hdr[off:off + 5], "big")
        x, y, ex, ey = v >> 30, (v >> 20) & 0x3FF, (v >> 10) & 0x3FF, v & 0x3FF
        return (x, y, ex - x + 1, ey - y + 1) if ex >= x and ey >= y else None
    n = 2 if layout == "wh" else 4
    if len(hdr) < off + 2 * n:
        return None
    f = [int.from_bytes(hdr[off + 2 * i:off + 2 * i + 2], order) for i in range(n)]
    if layout == "wh":
        return 0, 0, f[0], f[1]
    if layout == "box":
        return (f[0], f[1], f[2] - f[0] + 1, f[3] - f[1] + 1) if f[2] >= f[0] and f[3] >= f[1] else None
    return f[0], f[1], f[2], f[3]


def _fits(payload: int, n_pkts: int, room: int, size: int) -> bool:
    """The run's payload is `size` bytes, or `size` with the last packet padded to a full chunk."""
    return payload == size or (size < payload and n_pkts == -(-size // room) and payload - size < room)



def _region_tries(hl: int) -> list[tuple[str, int, str]]:
    """Region field layouts to try in a command of hl bytes, most likely first."""
    tries = [("box10", o, "big") for o in range(hl - 4)]
    for layout in ("xywh", "box", "wh"):
        # aligned little-endian fields first: a byte-shifted big-endian reading of small
        # values can fit the same frames
        tries += sorted(((layout, o, e) for o in range(hl - 1) for e in ("little", "big")),
                        key=lambda x: (x[1] % 2, x[2] != "little", x[1]))
    return tries


def _inline_region(runs: list[dict], min_frames: int) -> tuple | None:
    """A draw command at the start of each frame's first pixel packet (no packet of its own): its
    region fields give width x height, and the frame's bytes are that many pixels plus the command,
    the same command length in every frame. Returns (layout, offset, endian, format, got, length)."""
    if len(runs) < min_frames:
        return None
    width = {"box10": 5, "xywh": 8, "box": 8, "wh": 4}
    for layout, o, e in _region_tries(MAX_HEADER_PKT):
        for fmt, bpp in RAW.items():
            got, lens, misses = [], Counter(), 0
            room = 0.1 * len(runs) + 1   # runs that may miss (frames cut off by the capture)
            for r in runs:
                ps = list(r["pkts"])
                g = _region(layout, ps[0].data, o, e)
                if not g or not (0 < g[2] <= 4096 and 0 < g[3] <= 4096):
                    misses += 1
                    if misses > room:
                        break
                    continue
                pay = sum(len(t.data) for t in ps)
                hl = pay - g[2] * g[3] * bpp
                if not o + width[layout] <= hl <= MAX_HEADER_PKT and r["tail"] is not None:
                    ps.append(r["tail"])
                    hl += len(r["tail"].data)
                if o + width[layout] <= hl <= MAX_HEADER_PKT and hl <= len(ps[0].data):
                    got.append((r, ps, g, hl))
                    lens[hl] += 1
                else:
                    misses += 1
                    if misses > room:
                        break
            if not lens:
                continue
            hl, n = lens.most_common(1)[0]
            got = [(r, ps, g) for r, ps, g, k in got if k == hl]
            if n >= max(min_frames, 0.9 * len(runs)):
                if layout == "xywh" and not any(g[0] or g[1] for _, _, g in got):
                    continue   # x and y always 0: plain width and height fields are the simpler story
                return layout, o, e, fmt, got, hl
    return None

def _rgb565_order(pix: bytes) -> str | None:
    """Byte order of RGB565 pixels: the order that makes neighbouring pixels more alike, if clear."""
    n = min(len(pix) // 2, 8192)

    def cost(order):
        c, prev = 0, None
        for i in range(n):
            v = int.from_bytes(pix[2 * i:2 * i + 2], order)
            px = (v >> 11, (v >> 5) & 63, v & 31)
            if prev:
                c += 2 * abs(px[0] - prev[0]) + abs(px[1] - prev[1]) + 2 * abs(px[2] - prev[2])
            prev = px
        return c
    le, be = cost("little"), cost("big")
    if le < 0.7 * be:
        return "little"
    if be < 0.7 * le:
        return "big"
    return None


def _runs(pkts: list[Transfer], chunk: int) -> list[dict]:
    """Packets that follow each other without a pause, all but the last `chunk` bytes long, plus the
    short packet just before (a header candidate) and a short one just after (a tail candidate)."""
    runs, i = [], 0
    while i < len(pkts):
        n = len(pkts[i].data)
        if n <= MAX_HEADER_PKT or n > chunk:
            i += 1
            continue
        j = i + 1
        if n == chunk:
            while j < len(pkts) and pkts[j].ts - pkts[j - 1].ts < GAP and MAX_HEADER_PKT < len(pkts[j].data) <= chunk:
                j += 1
                if len(pkts[j - 1].data) < chunk:
                    break
        head = pkts[i - 1] if i and len(pkts[i - 1].data) <= MAX_HEADER_PKT and pkts[i].ts - pkts[i - 1].ts < GAP else None
        tail = pkts[j] if j < len(pkts) and len(pkts[j].data) <= MAX_HEADER_PKT and pkts[j].ts - pkts[j - 1].ts < GAP else None
        runs.append({"head": head, "pkts": pkts[i:j], "tail": tail})
        i = j
    return runs


def _frames_by_size(runs: list[dict], chunk: int, h: int) -> list[tuple[dict, list[Transfer], int]]:
    """Frames whose payload is a whole screen; a run of several back-to-back frames is split."""
    room = chunk - h
    out, sizes = [], Counter()
    for r in runs:
        pay = sum(len(t.data) - h for t in r["pkts"])
        for size in SIZES:
            if _fits(pay, len(r["pkts"]), room, size):
                sizes[size] += 1
                break
    big = [sz for sz, _ in sizes.most_common()] + sorted(SIZES, reverse=True)
    for r in runs:
        ps = r["pkts"]
        if h == 0 and chunk in SIZES and len(ps) > 1 and all(len(t.data) == chunk for t in ps):
            # one transfer per frame (the app hands the whole screen to the USB stack at once)
            out += [({"head": r["head"] if k == 0 else None, "pkts": [t], "tail": None}, [t], chunk)
                    for k, t in enumerate(ps)]
            continue
        pay = sum(len(t.data) - h for t in ps)
        hit = next((sz for sz in SIZES if _fits(pay, len(ps), room, sz)), None)
        if hit:
            out.append((r, ps, hit))
            continue
        # one run holding k frames sent back to back (each frame whole packets, no header packet)
        for sz in big:
            if sz % room == 0 and pay % sz == 0 and pay // sz >= 2 and all(len(t.data) == chunk for t in ps):
                per = sz // room
                out += [({"head": r["head"] if k == 0 else None, "pkts": ps[k:k + per], "tail": None},
                         ps[k:k + per], sz) for k in range(0, len(ps), per)]
                break
    return out


def _raw_stream(transfers: list[Transfer], key: tuple, pkts: list[Transfer], min_frames: int) -> dict | None:
    lens = Counter(len(t.data) for t in pkts if len(t.data) > MAX_HEADER_PKT)
    if not lens:
        return None
    chunk = lens.most_common(1)[0][0]
    runs = _runs(pkts, chunk)
    if not runs:
        return None
    # payload per packet after an optional per-packet header of h bytes
    best = None
    for h in range(0, MAX_HEADER + 1):
        if h >= chunk:
            break
        fr = _frames_by_size(runs, chunk, h)
        # runs that are one frame each are better evidence than runs split into several frames
        score = (sum(1 for r, ps, _ in fr if ps is r["pkts"]), len(fr))
        if len(fr) >= min_frames and (best is None or score > best[2]):
            best = (h, fr, score)
    h = best[0] if best else 0
    room = chunk - h
    # a header packet before the runs that says which region of the screen the pixels go to
    heads = Counter(len(r["head"].data) for r in runs if r["head"] is not None)
    region = None
    if heads and h == 0:
        hl, nh = heads.most_common(1)[0]
        headed = [r for r in runs if r["head"] is not None and len(r["head"].data) == hl]
        if nh >= min_frames:
            for layout, o, e in _region_tries(hl):
                for fmt, bpp in RAW.items():
                    got = []
                    for r in headed:
                        g = _region(layout, r["head"].data, o, e)
                        if not g or not (0 < g[2] <= 4096 and 0 < g[3] <= 4096):
                            break
                        ps = list(r["pkts"])
                        pay = sum(len(t.data) for t in ps)
                        if not _fits(pay, len(ps), room, g[2] * g[3] * bpp):
                            if r["tail"] is None or pay + len(r["tail"].data) != g[2] * g[3] * bpp:
                                continue
                            ps.append(r["tail"])
                        got.append((r, ps, g))
                    else:
                        if len(got) >= max(min_frames, 0.9 * len(headed)):
                            if layout == "xywh" and not any(g[0] or g[1] for _, _, g in got):
                                continue   # x and y always 0: plain width and height fields are the simpler story
                            region = (layout, o, e, fmt, got)
                            break
                if region:
                    break
    inline = 0   # length of a draw command sent at the start of the first pixel packet
    if region is None and h == 0:
        found = _inline_region(runs, min_frames)
        if found:
            region, inline = found[:5], found[5]
    if region:
        layout, o, e, fmt, got = region
        frames = [ps for _, ps, _ in got]
        heads_used = [] if inline else [r["head"] for r, _, _ in got]
        areas = Counter((g[0], g[1], g[2], g[3]) for _, _, g in got)
        full = max(areas, key=lambda g: (g[2] * g[3], areas[g]))
        size, alts = [full[2], full[3]], []
        n_regions = sum(1 for _, _, g in got if (g[2], g[3]) != (full[2], full[3]))
        frame_bytes = full[2] * full[3] * RAW[fmt]
    else:
        if best is None:
            return None
        got = best[1]
        frames = [ps for _, ps, _ in got]
        heads_used = [r["head"] for r, _, _ in got if r["head"] is not None]
        frame_bytes = Counter(sz for _, _, sz in got).most_common(1)[0][0]
        (fmt, w, hh), *rest = SIZES[frame_bytes]
        size, n_regions = [w, hh], 0
        alts = [f"{f} {a}x{b}" for f, a, b in rest]
        if heads_used and len(heads_used) < 0.8 * len(frames):
            heads_used = []
    ids = {id(t) for f in frames for t in f} | {id(t) for t in heads_used}
    # frames cut off by the start or the end of the capture: the first or last run, same chunk size
    used = {id(r["pkts"][0]) for r, _, _ in got}
    partial = [t for r in (runs[0], runs[-1]) if id(r["pkts"][0]) not in used for t in r["pkts"]
               if len(t.data) == chunk]
    if inline:   # a cut frame still ends with the short rest of its pixels
        partial += [r["tail"] for r in (runs[0], runs[-1]) if id(r["pkts"][0]) not in used
                    and r["tail"] is not None and len(r["tail"].data) < chunk]
    ids |= {id(t) for t in partial}
    first, froles = _header(frames, h, True)
    nxt, nroles = _header([f for f in frames if len(f) > 1], h, False)
    pix = b"".join(t.data[h:] for t in frames[0])[inline:inline + frame_bytes] if frames else b""
    full_frames = [f for f in frames if sum(len(t.data) - h for t in f) - inline >= frame_bytes]
    if full_frames:
        pix = b"".join(t.data[h:] for t in full_frames[0])[inline:inline + frame_bytes]
    span = frames[-1][0].ts - frames[0][0].ts
    plens = Counter(len(t.data) for f in frames for t in f)
    s = {"endpoint": key[1], "xfer_type": key[2], "format": fmt, "frames": len(frames),
         "packets": len(ids), "partial": len(partial), "chunk": chunk,
         "padded": plens[chunk] >= 0.95 * sum(plens.values()) and any(
             sum(len(t.data) - h for t in f) - inline > frame_bytes for f in frames),
         "header_len": h, "first_header": first if h else "", "next_header": nxt if h else "",
         "count_offset": froles.get("count", nroles.get("count")),
         "index_offset": nroles.get("index"), "index_base": nroles.get("index_base"),
         "count_in_next": "count" in nroles,
         "count_width": froles.get("count_width", nroles.get("count_width")),
         "count_endian": froles.get("count_endian", nroles.get("count_endian")),
         "index_width": nroles.get("index_width"), "index_endian": nroles.get("index_endian"),
         "packets_per_frame": [min(map(len, frames)), max(map(len, frames))],
         "image_bytes": [min(sum(len(t.data) - h for t in f) for f in frames) - inline,
                         max(sum(len(t.data) - h for t in f) for f in frames) - inline],
         "size": size, "size_alternatives": alts, "frame_bytes": frame_bytes, "regions": n_regions,
         "fps": round((len(frames) - 1) / span, 1) if span > 0 else None,
         "first_frames": [f[0].frame for f in frames[:5]], "ack": None, "raw": True,
         "byteorder": _rgb565_order(pix) if fmt == "rgb565" else None,
         "header_packet": None, "header_inline": bool(inline), "region": None, "length_field": None}
    s.update(_channel_order(full_frames, h, fmt, frame_bytes, s["byteorder"], skip=inline))
    if heads_used or inline:
        hd = [f[0].data[:inline] for f in frames] if inline else [t.data for t in heads_used]
        hl = len(hd[0])
        tokens: list[str | None] = [None] * hl
        if region:
            layout, o, e = region[:3]
            if layout == "box10":
                tokens[o:o + 5] = ["rr"] * 5
            else:
                for i, name in enumerate(REGION_TOKENS[layout]):
                    tokens[o + 2 * i:o + 2 * i + 2] = [name, name]
            s["region"] = {"layout": layout, "offset": o, "endian": e}
        # a 16- or 32-bit field holding the frame's byte count
        pays = [sum(len(t.data) - h for t in f) - inline for f in frames]
        for width in (4, 2):
            for j in range(hl - width + 1):
                if s["length_field"] or any(tokens[j:j + width]):
                    continue
                for e in ("little", "big"):
                    vals = [int.from_bytes(d[j:j + width], e) for d in hd]
                    if max(vals) > 255 and all(v == p for v, p in zip(vals, pays)):
                        tokens[j:j + width] = ["ll"] * width
                        s["length_field"] = {"offset": j, "width": width, "endian": e}
                        break
        for j in range(hl):
            if tokens[j] is None:
                col = {d[j] for d in hd}
                tokens[j] = f"{col.pop():02x}" if len(col) == 1 else "??"
        s["header_packet"] = " ".join(tokens)
    _add_ack(s, transfers, key[0], frames, ids)
    s["ids"] = ids
    s.update(_frames=frames, _heads=heads_used, _complete=len(frames))
    return s


# ---- channel order (RGB or BGR) from the usb-rea test card ----
#
# Pixels alone do not say whether the first channel is red or blue: a photo with red and blue
# swapped is still a smooth photo. So the order is only claimed when a frame shows a known picture,
# the usb-rea test card (`usb-rea testcard`): left half red, top right quarter green, then a blue
# and a white eighth. Its colour shares (1/2 red, 1/4 green, 1/8 blue, 1/8 white) do not change
# when the vendor app scales, rotates or mirrors the picture, and they only come out right for one
# reading of the pixels (RGB or BGR, and for RGB565 also little or big endian). Without such a
# frame the order stays unknown.

TESTCARD_SHARES = {"r": 0.5, "g": 0.25, "b": 0.125, "w": 0.125}
TESTCARD_COLORS = {"r": (255, 0, 0), "g": (0, 255, 0), "b": (0, 0, 255), "w": (255, 255, 255)}
_LO, _HI = 55, 200   # a channel this dark or this bright counts as off or on


def testcard(w: int, h: int) -> bytes:
    """The test card as RGB888 pixels, row by row."""
    out = bytearray()
    for y in range(h):
        for x in range(w):
            c = "r" if x < w // 2 else "g" if y < h // 2 else "b" if x < w * 3 // 4 else "w"
            out += bytes(TESTCARD_COLORS[c])
    return bytes(out)


def write_testcard(path, w: int = 320, h: int = 240) -> None:
    """Save the test card as a PNG (no Pillow needed) to show on the screen while capturing."""
    import struct
    import zlib
    pix = testcard(w, h)
    rows = b"".join(b"\x00" + pix[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def _readings(fmt: str) -> list[tuple[str, str | None]]:
    return [(o, e) for o in ("rgb", "bgr") for e in ((None,) if fmt == "rgb888" else ("little", "big"))]


def _pixel(fmt: str, px: bytes, order: str, endian: str | None) -> tuple[int, int, int]:
    if fmt == "rgb888":
        a, g, c = px[0], px[1], px[2]
    else:
        v = int.from_bytes(px, endian)
        a, g, c = (v >> 11) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31
    return (a, g, c) if order == "rgb" else (c, g, a)


def _color(p: tuple[int, int, int]) -> str | None:
    if all(v >= _HI for v in p):
        return "w"
    on = [v >= _HI for v in p]
    if sum(on) == 1 and all(v <= _LO for v, o in zip(p, on) if not o):
        return "rgb"[on.index(True)]
    return None


def _is_testcard(fmt: str, pix: bytes, order: str, endian: str | None, n: int) -> bool:
    bpp = RAW[fmt]
    total = len(pix) // bpp
    if total < 16:
        return False
    # spread the samples with the golden ratio: a plain stride can land on the same column every row
    got = Counter(_color(_pixel(fmt, pix[i * bpp:(i + 1) * bpp], order, endian))
                  for i in (int(total * (k * 0.6180339887 % 1)) for k in range(n)))
    if sum(v for k, v in got.items() if k) < 0.85 * n:
        return False
    return all(abs(got[c] / n - share) <= (0.1 if share > 0.2 else 0.06) for c, share in TESTCARD_SHARES.items())


def _channel_order(frames: list[list[Transfer]], h: int, fmt: str, frame_bytes: int,
                   byteorder: str | None, max_frames: int = 600, skip: int = 0) -> dict:
    """`channel_order` ('rgb', 'bgr' or None for unknown) and the evidence: full frames that show
    the test card under exactly one reading of the pixels. For RGB565 the test card also settles the
    byte order (`byteorder` is replaced when the pixel smoothness guess disagreed). Confidence is
    the share of matching frames that agree; below 0.9 the order stays unknown."""
    hits: Counter = Counter()
    seen: dict[tuple, list[int]] = {}
    checked = 0
    # a long video is checked at an even stride (a card shown for a few seconds is still hit)
    for f in frames[::max(1, -(-len(frames) // max_frames))]:
        pix = b"".join(t.data[h:] for t in f)[skip:skip + frame_bytes]
        checked += 1
        # a quick look at a few pixels first, the full sample only for likely frames
        quick = [r for r in _readings(fmt) if _is_testcard(fmt, pix, *r, 64)]
        match = [r for r in quick if _is_testcard(fmt, pix, *r, 2048)]
        if len(match) == 1:
            hits[match[0]] += 1
            seen.setdefault(match[0], []).append(f[0].frame)
    out = {"channel_order": None, "channel_evidence": None}
    if not hits:
        return out
    (order, endian), n = hits.most_common(1)[0]
    matched = sum(hits.values())
    conf = round(n / matched, 2)
    out["channel_evidence"] = {"method": "testcard", "frames_checked": checked, "frames_matched": matched,
                               "agree": n, "confidence": conf, "frames": seen[(order, endian)][:5],
                               "byteorder": endian}
    if conf >= 0.9:
        out["channel_order"] = order
        if endian:
            out["byteorder"] = endian
            out["channel_evidence"]["byteorder_was"] = byteorder
    return out
