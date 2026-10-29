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
    """Pattern of the first (or the following) packets' headers: hex, nn = packet count, ii = index."""
    rows = [(f[0].data[:h], len(f), 0) for f in frames] if first else \
        [(t.data[:h], len(f), k) for f in frames for k, t in enumerate(f[1:], 1)]
    if not rows:
        return "", {}
    counts = {n for _, n, _ in rows}
    out, roles = [], {}
    for j in range(h):
        vals = [d[j] for d, _, _ in rows]
        if len(counts) > 1 and all(v == n & 0xFF for v, (_, n, _) in zip(vals, rows)):
            out.append("nn")
            roles["count"] = j
        elif not first and len({v - k for v, (_, _, k) in zip(vals, rows)}) == 1 and len(set(vals)) > 1:
            out.append("ii")
            roles["index"], roles["index_base"] = j, vals[0] - rows[0][2]
        elif len(set(vals)) == 1:
            out.append(f"{vals[0]:02x}")
        else:
            out.append("??")
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
        # a fixed device->host message sent about once per frame on the same device is the frame ack
        acks: dict[tuple, list[Transfer]] = {}
        for t in transfers:
            if t.is_in and t.data and t.device == key[0] and t.xfer_type in (1, 3):
                acks.setdefault((t.endpoint, t.data), []).append(t)
        fit = [(ep, d, g) for (ep, d), g in acks.items() if 0.5 * len(frames) <= len(g) <= 1.2 * len(frames)]
        if fit:
            ep, d, g = max(fit, key=lambda x: len(x[2]))
            s["ack"] = {"endpoint": ep, "payload": d.hex(" "), "count": len(g), "frames": [t.frame for t in g[:5]]}
            ids |= {id(t) for t in g}
        s["ids"] = ids
        found.append(s)
    return found


def drop_streams(transfers: list[Transfer], streams: list[dict]) -> list[Transfer]:
    ids = set().union(*(s["ids"] for s in streams)) if streams else set()
    return [t for t in transfers if id(t) not in ids]


def describe(s: dict) -> str:
    """One line: 'jpeg stream on interrupt EP 0x03: 8670 frames, ...'."""
    from .model import XFER_NAMES
    size = f" {s['size'][0]}x{s['size'][1]}," if s["size"] else ""
    ack = f"; ack {s['ack']['payload']} on EP 0x{s['ack']['endpoint']:02x}" if s["ack"] else ""
    hdr = f", header `{s['first_header']}` then `{s['next_header']}`" if s["header_len"] else ""
    return (f"{s['format']} stream on {XFER_NAMES.get(s['xfer_type'])} EP 0x{s['endpoint']:02x}:{size} "
            f"{s['frames']} frames in {s['packets']} packets of {s['chunk']} bytes{hdr}{ack}")
