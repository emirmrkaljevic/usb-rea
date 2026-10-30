"""Continuous image streams (pictures or video for an LCD) kept apart from commands.

Some devices with a screen (AIO pump caps, keyboards and stream decks with displays) get a picture
or a whole video from the vendor app: thousands of large host->device packets on one endpoint, each
frame an encoded image cut into chunks behind a small per-packet header. Diffed as actions, that
traffic drowns the real commands (brightness, orientation) sent on another endpoint.

A stream is a host->device channel (bulk or interrupt) where at least `min_frames` packets start
an image (JPEG FF D8 FF, PNG 89 50 4E 47 0D 0A 1A 0A, GIF 'GIF8') at the same offset. That offset
is the per-packet header length. A frame runs from its start packet until the image end marker
(JPEG FF D9, PNG IEND), the next start or a pause of a second; its packets are set aside.
Header bytes are described as constant, `nn` (the number of packets in the frame) or `ii` (the
packet's index in the frame), and a device->host message of fixed content sent about once per
frame is recorded as the per-frame ack.

Raw pixel streams (RGB565, RGB888) have no start marker and are found by size instead, see the
section further down.
"""
from __future__ import annotations
from collections import Counter

from .model import Transfer

MAGIC = {"jpeg": b"\xff\xd8\xff", "png": b"\x89PNG\r\n\x1a\n", "gif": b"GIF8"}
END = {"jpeg": b"\xff\xd9", "png": b"IEND\xaeB`\x82"}
MAX_HEADER = 32


def _size(fmt: str, img: bytes) -> tuple[int, int] | None:
    """(width, height) from a JPEG SOF marker, the PNG IHDR or the GIF screen descriptor."""
    if fmt == "png" and len(img) >= 24:
        return int.from_bytes(img[16:20], "big"), int.from_bytes(img[20:24], "big")
    if fmt == "gif" and len(img) >= 10:
        return int.from_bytes(img[6:8], "little"), int.from_bytes(img[8:10], "little")
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
    embedded thumbnail does not end the frame), else None."""
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


def find_streams(transfers: list[Transfer], min_frames: int = 3) -> list[dict]:
    """Image streams in the capture; each dict has the stream's description plus `ids` (its packets
    and acks, to leave out of everything else)."""
    chans: dict[tuple, list[Transfer]] = {}
    for t in sorted(transfers, key=lambda t: t.ts):
        if t.is_out and t.data and t.xfer_type in (1, 3):
            chans.setdefault(t.key(), []).append(t)
    found = []
    for key, pkts in chans.items():
        best = None
        for fmt, magic in MAGIC.items():
            offs = Counter(t.data.find(magic) for t in pkts)
            offs.pop(-1, None)
            offs = Counter({o: n for o, n in offs.items() if o <= MAX_HEADER})
            if offs:
                h, n = offs.most_common(1)[0]
                if n >= min_frames and (best is None or n > best[2]):
                    best = (fmt, h, n)
        if best is None:
            continue
        fmt, h, _ = best
        magic = MAGIC[fmt]
        starts = [i for i, t in enumerate(pkts) if t.data[h:h + len(magic)] == magic]
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
        s.update(raw=False, header_packet=None, region=None, length_field=None, byteorder=None,
                 size_alternatives=[], frame_bytes=None, regions=0)
        _add_ack(s, transfers, key[0], len(frames), ids)
        s["ids"] = ids
        found.append(s)
    taken = {(s["endpoint"], s["xfer_type"]) for s in found}
    for key, pkts in chans.items():
        if (key[1], key[2]) not in taken:
            r = _raw_stream(transfers, key, pkts, min_frames)
            if r:
                found.append(r)
    return found


def _add_ack(s: dict, transfers: list[Transfer], device: int, n_frames: int, ids: set) -> None:
    """A fixed device->host message sent about once per frame on the same device is the frame ack."""
    acks: dict[tuple, list[Transfer]] = {}
    for t in transfers:
        if t.is_in and t.data and t.device == device and t.xfer_type in (1, 3):
            acks.setdefault((t.endpoint, t.data), []).append(t)
    fit = [(ep, d, g) for (ep, d), g in acks.items() if 0.5 * n_frames <= len(g) <= 1.2 * n_frames]
    if fit:
        ep, d, g = max(fit, key=lambda x: len(x[2]))
        s["ack"] = {"endpoint": ep, "payload": d.hex(" "), "count": len(g), "frames": [t.frame for t in g[:5]]}
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
    kind = f"raw {s['format']}{order}" if s.get("raw") else s["format"]
    return (f"{kind} stream on {XFER_NAMES.get(s['xfer_type'])} EP 0x{s['endpoint']:02x}:{size} "
            f"{s['frames']} frames{part} in {s['packets']} packets of {s['chunk']} bytes{hdr}{ack}")


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
            tries = [("box10", o, "big") for o in range(hl - 4)]
            for layout in ("xywh", "box", "wh"):
                # aligned little-endian fields first: a byte-shifted big-endian reading of small
                # values can fit the same frames
                tries += sorted(((layout, o, e) for o in range(hl - 1) for e in ("little", "big")),
                                key=lambda x: (x[1] % 2, x[2] != "little", x[1]))
            for layout, o, e in tries:
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
    if region:
        layout, o, e, fmt, got = region
        frames = [ps for _, ps, _ in got]
        heads_used = [r["head"] for r, _, _ in got]
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
    ids |= {id(t) for t in partial}
    first, froles = _header(frames, h, True)
    nxt, nroles = _header([f for f in frames if len(f) > 1], h, False)
    pix = b"".join(t.data[h:] for t in frames[0])[:frame_bytes] if frames else b""
    full_frames = [f for f in frames if sum(len(t.data) - h for t in f) >= frame_bytes]
    if full_frames:
        pix = b"".join(t.data[h:] for t in full_frames[0])[:frame_bytes]
    span = frames[-1][0].ts - frames[0][0].ts
    plens = Counter(len(t.data) for f in frames for t in f)
    s = {"endpoint": key[1], "xfer_type": key[2], "format": fmt, "frames": len(frames),
         "packets": len(ids), "partial": len(partial), "chunk": chunk,
         "padded": plens[chunk] >= 0.95 * sum(plens.values()) and any(
             sum(len(t.data) - h for t in f) > frame_bytes for f in frames),
         "header_len": h, "first_header": first if h else "", "next_header": nxt if h else "",
         "count_offset": froles.get("count", nroles.get("count")),
         "index_offset": nroles.get("index"), "index_base": nroles.get("index_base"),
         "count_in_next": "count" in nroles,
         "count_width": froles.get("count_width", nroles.get("count_width")),
         "count_endian": froles.get("count_endian", nroles.get("count_endian")),
         "index_width": nroles.get("index_width"), "index_endian": nroles.get("index_endian"),
         "packets_per_frame": [min(map(len, frames)), max(map(len, frames))],
         "image_bytes": [min(sum(len(t.data) - h for t in f) for f in frames),
                         max(sum(len(t.data) - h for t in f) for f in frames)],
         "size": size, "size_alternatives": alts, "frame_bytes": frame_bytes, "regions": n_regions,
         "fps": round((len(frames) - 1) / span, 1) if span > 0 else None,
         "first_frames": [f[0].frame for f in frames[:5]], "ack": None, "raw": True,
         "byteorder": _rgb565_order(pix) if fmt == "rgb565" else None,
         "header_packet": None, "region": None, "length_field": None}
    if heads_used:
        hd = [t.data for t in heads_used]
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
        pays = [sum(len(t.data) - h for t in f) for f in frames]
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
    _add_ack(s, transfers, key[0], len(frames), ids)
    s["ids"] = ids
    return s
