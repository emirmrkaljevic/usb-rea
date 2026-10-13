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
