"""Case study: Corsair Hydro H100i Platinum (1b1c:0c18), cooling command as built by liquidctl.

Reference: https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py
_send_command(): [0x3f, seq << 3 | feature, command, data..., crc8(buf[1:-1])], 64 bytes,
crc-8 = poly 0x07, sequence 1..31. _generate_cooling_payload(): fan1 mode at data[8],
fan1 duty at data[13] (percent of 255), pump mode at data[20].
See docs/case-study-hydro-platinum.md.
"""
from usb_rea.pipeline import analyze
from usb_rea.synth import capture_from_messages


def crc8(b):
    c = 0
    for x in b:
        c ^= x
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c


def cooling(seq, fan1, pump=1, fan2=100):
    d = bytearray(60)
    d[0:8] = [0x00, 0xFF, 0x05, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
    d[26] = 7
    d[8], d[13] = 2, round(fan1 / 100 * 255)
    d[14], d[19] = 2, round(fan2 / 100 * 255)
    d[20] = pump
    w = bytearray(64)
    w[0], w[1], w[2] = 0x3F, (seq << 3) | 0b000, 0x14
    w[3:63] = d
    w[63] = crc8(w[1:63])
    return bytes(w)


def test_hydro_platinum_cooling(tmp_path):
    msgs, seq = [], 0
    for v in (50, 20, 100, 35, 80, 65, 50):
        seq += 1
        msgs.append((f"fan1 {v}%", cooling(seq, v), ("interrupt", 0x01)))
    for m in (0, 2, 1, 0, 2):
        seq += 1
        msgs.append((f"pump mode {m}", cooling(seq, 50, pump=m), ("interrupt", 0x01)))
    cap, _ = capture_from_messages(tmp_path / "h100i.pcap", msgs, 0x1B1C, 0x0C18)
    p = analyze(cap)
    c = {x.name: x for x in p.commands}
    fan = {f.offset: f for f in c["fan1"].fields}
    assert fan[0].const == 0x3F and fan[2].const == 0x14
    assert fan[1].kind == "counter" and fan[1].step == 8
    assert fan[16].kind == "value" and abs(fan[16].scale - 2.55) < 1e-9
    assert fan[63].kind == "checksum" and fan[63].algo == "crc8" and fan[63].covers == (1, 63)
    pump = {f.offset: f for f in c["pump mode"].fields}
    assert pump[23].kind == "value"
    # never-captured duty and sequence number: byte-identical to liquidctl's framing
    assert c["fan1"].encode(42, seq=13) == cooling(13, 42)
    assert c["pump mode"].encode(2, seq=21) == cooling(21, 50, pump=2)
