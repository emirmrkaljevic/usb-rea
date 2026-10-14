import importlib.util
from unittest import mock

from usb_rea.pipeline import analyze
from usb_rea.scaffold import generate
from usb_rea.synth import make_capture, encode_fan


def proto(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan")
    return analyze(cap), cap


def test_fan_fields(tmp_path):
    p, _ = proto(tmp_path)
    c = {c.name: c for c in p.commands}
    assert set(c) == {"fan", "color", "mode"}
    fan = {f.offset: f for f in c["fan"].fields}
    assert fan[1].kind == "counter" and fan[1].step == 1
    assert fan[2].kind == "command"
    assert fan[3].kind == "value" and fan[3].width == 2 and fan[3].endian == "be" and fan[3].scale == 1
    assert fan[6].kind == "checksum" and fan[6].algo == "crc16_modbus" and fan[6].width == 2
    col = {f.offset: f for f in c["color"].fields}
    assert [(col[i].kind, col[i].index) for i in (3, 4, 5)] == [("value", 0), ("value", 1), ("value", 2)]
    mode = {f.offset: f for f in c["mode"].fields}
    assert mode[3].kind == "lookup" and mode[3].table == {1.0: 0x11, 2.0: 0x22, 3.0: 0x47}
    for cmd in c.values():
        assert cmd.confidence == 1.0


def test_fan_encode_unseen_values(tmp_path):
    p, _ = proto(tmp_path)
    c = {c.name: c for c in p.commands}
    assert c["fan"].encode(3100, seq=7) == encode_fan("fan", [3100], 7)
    assert c["color"].encode(1, 2, 3, seq=9) == encode_fan("color", [1, 2, 3], 9)
    assert c["mode"].encode(2, seq=1) == encode_fan("mode", [2], 1)


def test_fan_driver(tmp_path):
    p, _ = proto(tmp_path)
    path = tmp_path / "fan_drv.py"
    path.write_text(generate(p))
    spec = importlib.util.spec_from_file_location("fan_drv", path)
    drv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drv)
    sent = []
    fake = mock.MagicMock()
    fake.__iter__.return_value = []
    fake.write.side_effect = lambda ep, data: sent.append(bytes(data)) or len(data)
    d = drv.Device(fake)
    d.set_fan(1500)
    d.set_color(9, 8, 7)
    assert sent == [encode_fan("fan", [1500], 1), encode_fan("color", [9, 8, 7], 2)]


def dial_proto(tmp_path):
    cap, _ = make_capture(tmp_path / "dial.pcap", device="dial")
    return analyze(cap), cap


def test_dial_u32_and_bitfield(tmp_path):
    from usb_rea.synth import encode_dial
    p, _ = dial_proto(tmp_path)
    c = {cmd.name: cmd for cmd in p.commands}
    assert set(c) == {"position", "level"}

    pos = {f.offset: f for f in c["position"].fields}
    assert pos[0].kind == "const" and pos[0].const == 0xA5
    assert pos[1].kind == "command" and pos[1].const == 0x01
    assert pos[2].kind == "value" and pos[2].width == 4 and pos[2].endian == "le"
    assert pos[2].scale == 1 and pos[2].bias == 0
    assert pos[6].kind == "checksum" and pos[6].algo == "sum8"
    assert c["position"].encode(0x11223344) == encode_dial("position", [0x11223344])

    lvl = {f.offset: f for f in c["level"].fields}
    assert lvl[0].kind == "const" and lvl[0].const == 0xA5
    assert lvl[1].kind == "command" and lvl[1].const == 0x02
    bf = lvl[2]
    assert bf.kind == "bitfield" and bf.bit_offset == 0 and bf.bit_width == 4
    assert bf.scale == 1 and bf.bias == 0
    assert c["level"].encode(9) == encode_dial("level", [9])
    assert c["level"].encode(15) == encode_dial("level", [15])
    for cmd in c.values():
        assert cmd.confidence == 1.0


def test_dial_driver_roundtrip(tmp_path):
    from usb_rea.synth import encode_dial
    p, _ = dial_proto(tmp_path)
    path = tmp_path / "dial_drv.py"
    path.write_text(generate(p))
    spec = importlib.util.spec_from_file_location("dial_drv", path)
    drv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drv)
    sent = []
    fake = mock.MagicMock()
    fake.__iter__.return_value = []
    fake.write.side_effect = lambda ep, data: sent.append(bytes(data)) or len(data)
    d = drv.Device(fake)
    d.set_position(0xAABBCCDD)
    d.set_level(12)
    assert sent == [encode_dial("position", [0xAABBCCDD]), encode_dial("level", [12])]


def test_u32_be_direct():
    """32-bit big-endian value without going through synth capture."""
    from usb_rea.infer import infer
    from usb_rea.model import Action, Transfer
    acts = []
    for i, v in enumerate([0, 0x01020304, 0x0A0B0C0D, 0x10203040, 0x7F7F7F7F]):
        body = bytes([0xCC, 0x01]) + v.to_bytes(4, "big")
        t = Transfer(i + 1, float(i), 1, 3, 0x01, 3, None, body)
        acts.append(Action(f"count {v}", i - 0.1, i + 0.1, [t]))
    c = infer(acts).commands[0]
    f = next(x for x in c.fields if x.kind == "value")
    assert f.width == 4 and f.endian == "be" and f.scale == 1
    assert c.encode(0x11223344) == bytes([0xCC, 0x01]) + (0x11223344).to_bytes(4, "big")


def test_bitfield_across_two_bytes():
    """12-bit value packed in bits 0..11 of a little-endian 16-bit word; high nibble const."""
    from usb_rea.infer import infer
    from usb_rea.model import Action, Transfer
    acts = []
    for i, v in enumerate([0, 100, 500, 2047, 3000]):
        # bits 0-11 = v, bits 12-15 = 0x5
        word = 0x5000 | (v & 0x0FFF)
        body = bytes([0xDD, word & 0xFF, word >> 8])
        t = Transfer(i + 1, float(i), 1, 3, 0x01, 3, None, body)
        acts.append(Action(f"gain {v}", i - 0.1, i + 0.1, [t]))
    c = infer(acts).commands[0]
    bf = next(x for x in c.fields if x.kind == "bitfield")
    assert bf.offset == 1 and bf.width == 2
    assert bf.bit_offset == 0 and bf.bit_width == 12
    assert c.encode(1500) == bytes([0xDD, 0xDC, 0x55])  # 0x5000|1500 = 0x55DC
