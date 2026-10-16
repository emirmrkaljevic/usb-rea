"""Multi-packet transactions: an action that sends several packets (e.g. set + commit)."""
import importlib.util
from unittest import mock

from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.scaffold import generate
from usb_rea.synth import capture_from_messages

EP = ("bulk", 0x02)


def lcd(name, *v):
    if name == "backlight":   # write value, then a constant "apply" packet
        return [bytes([0x12, 0x34, int(v[0]), 0x00]), bytes([0x12, 0x99, 0x01, 0x00])]
    if name == "color":       # select register, write RGB, apply with sum8 checksum
        rgb = bytes(int(x) for x in v)
        return [bytes([0x20, 0x01]), bytes([0x21]) + rgb, bytes([0x22, sum(rgb) & 0xFF])]
    return [bytes([0x30, int(v[0])])]   # rotate: single packet


ACTIONS = [("backlight", 0), ("backlight", 40), ("backlight", 100), ("color", 255, 0, 0),
           ("color", 0, 128, 255), ("color", 9, 8, 7), ("rotate", 0), ("rotate", 1), ("rotate", 2)]


def capture(tmp_path):
    msgs = [(" ".join([a[0], *map(str, a[1:])]), lcd(*a), EP) for a in ACTIONS]
    cap, _ = capture_from_messages(tmp_path / "lcd.pcap", msgs, 0x1234, 0x5678)
    return analyze(cap), cap


def test_transaction_structure(tmp_path):
    p, _ = capture(tmp_path)
    c = {c.name: c for c in p.commands}
    assert set(c) == {"backlight", "color", "rotate"}
    assert len(c["backlight"].steps) == 1 and len(c["color"].steps) == 2 and c["rotate"].steps == []
    assert all(x.confidence == 1.0 for x in p.commands)
    commit = {f.offset: f for f in c["color"].steps[1].fields}
    assert commit[1].kind == "checksum" and commit[1].source == 1 and commit[1].algo == "sum8"


def test_transaction_encodes_unseen_values(tmp_path):
    p, _ = capture(tmp_path)
    c = {c.name: c for c in p.commands}
    assert c["backlight"].encode_all(70) == lcd("backlight", 70)
    assert c["color"].encode_all(1, 2, 3) == lcd("color", 1, 2, 3)
    assert c["rotate"].encode_all(3) == lcd("rotate", 3)


def test_transaction_report_and_driver(tmp_path):
    p, cap = capture(tmp_path)
    md = render(p, str(cap))
    assert "## `color [packet 3]`" in md and "multi-packet transaction: 3 packets" in md
    path = tmp_path / "lcd_drv.py"
    path.write_text(generate(p))
    spec = importlib.util.spec_from_file_location("lcd_drv", path)
    drv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drv)
    sent = []
    fake = mock.MagicMock()
    fake.__iter__.return_value = []
    fake.write.side_effect = lambda ep, data: sent.append(bytes(data)) or len(data)
    d = drv.Device(fake)
    d.set_color(10, 20, 30)
    d.set_backlight(55)
    assert sent == lcd("color", 10, 20, 30) + lcd("backlight", 55)
