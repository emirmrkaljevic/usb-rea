from usb_rea.pcap import read_transfers, find_ids
from usb_rea.synth import make_capture, encode, VID, PID


def test_parse_synthetic(tmp_path):
    cap, _ = make_capture(tmp_path / "lamp.pcap")
    ts = read_transfers(cap)
    outs = [t for t in ts if t.is_out and t.data]
    assert len(outs) == 10
    assert outs[2].data == encode("brightness", 50)
    assert outs[2].endpoint == 0x01 and outs[2].kind == "bulk"
    assert find_ids(ts) == {5: (VID, PID)}
    # frame numbers are 1-based and increasing
    assert ts[0].frame >= 1 and all(a.frame < b.frame for a, b in zip(ts, ts[1:]))


def test_parse_control_transport(tmp_path):
    cap, _ = make_capture(tmp_path / "lamp.pcap", transport="control")
    outs = [t for t in read_transfers(cap) if t.is_out and t.data]
    assert outs[0].kind == "control" and outs[0].setup[:2] == b"\x21\x09"
    assert outs[0].data[0] == 0xAA


def test_pcapng(tmp_path):
    import struct
    cap, _ = make_capture(tmp_path / "lamp.pcap", noise=False)
    raw = cap.read_bytes()
    # convert pcap -> pcapng by hand
    def blk(t, body):
        body += b"\x00" * (-len(body) % 4)
        n = 12 + len(body)
        return struct.pack("<II", t, n) + body + struct.pack("<I", n)
    out = blk(0x0A0D0D0A, struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1))
    out += blk(1, struct.pack("<HHI", 220, 0, 65535))
    off = 24
    while off < len(raw):
        s, us, inc, orig = struct.unpack("<IIII", raw[off:off + 16])
        tsv = s * 1_000_000 + us
        out += blk(6, struct.pack("<IIIII", 0, tsv >> 32, tsv & 0xFFFFFFFF, inc, orig) + raw[off + 16:off + 16 + inc])
        off += 16 + inc
    p = tmp_path / "lamp.pcapng"
    p.write_bytes(out)
    a = [t.data for t in read_transfers(cap)]
    b = [t.data for t in read_transfers(p)]
    assert a == b
