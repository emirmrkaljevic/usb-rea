"""Continuous image streams (pictures or video for an LCD) kept apart from the commands."""
import importlib.util
import sys
from unittest import mock

import pytest

from usb_rea.model import Transfer
from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.scaffold import generate
from usb_rea.streams import _size, find_streams
from usb_rea.synth import LCD_ACTIONS, fake_jpeg, lcd_frames, make_capture


def test_stream_found_and_brightness_kept_on_its_own_endpoint(tmp_path):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True)
    proto = analyze(cap)
    assert [(c.name, c.endpoint, c.confidence) for c in proto.commands] == [("brightness", 0x01, 1.0)]
    value = [f for f in proto.commands[0].fields if f.kind == "value"]
    assert [(f.offset, f.scale, f.bias) for f in value] == [(4, 1.0, 0.0)]
    [s] = proto.streams
    assert (s["endpoint"], s["xfer_type"], s["format"], s["chunk"], s["padded"]) == (0x03, 1, "jpeg", 512, True)
    assert (s["header_len"], s["first_header"], s["next_header"]) == (4, "08 nn 00 80", "08 ii 00 00")
    assert (s["count_offset"], s["index_offset"], s["index_base"]) == (1, 1, 0)
    assert s["size"] == [240, 240] and s["fps"] == 20.0 and s["partial"] >= 1
    assert s["ack"]["endpoint"] == 0x84 and s["ack"]["payload"].startswith("08 81 00")
    # the acks are not taken for replies to the brightness command
    assert proto.responses == [] and proto.background == []
    assert "ids" not in proto.to_dict()["streams"][0]


def test_labels_mode_splits_only_the_commands(tmp_path):
    # no markers: the pauses between brightness writes still show, the video runs through them
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True)
    proto = analyze(cap, markers=tmp_path / "none.json", labels=LCD_ACTIONS)
    assert [(c.name, c.confidence) for c in proto.commands] == [("brightness", 1.0)]
    assert [x[0] for x in proto.commands[0].samples] == LCD_ACTIONS


def test_without_stream_nothing_changes(tmp_path):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd")
    proto = analyze(cap)
    assert proto.streams == [] and [c.name for c in proto.commands] == ["brightness"]
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", poll=0.5)
    assert analyze(cap).streams == []
    with pytest.raises(ValueError):
        make_capture(tmp_path / "x.pcap", device="fan", image_stream=True)


def test_report_and_driver(tmp_path):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True)
    proto = analyze(cap)
    md = render(proto)
    assert "## Image stream on interrupt EP 0x03 (kept out of the commands)" in md
    assert "first packet `08 nn 00 80`, then `08 ii 00 00`" in md and "Image size: 240x240" in md
    src = generate(proto)
    assert "def send_image(self, image" in src and "STREAMS = " in src
    path = tmp_path / "lcd_driver.py"
    path.write_text(src)
    usb = mock.MagicMock()
    with mock.patch.dict(sys.modules, {"usb": usb, "usb.core": usb.core}):
        spec = importlib.util.spec_from_file_location("lcd_driver", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    dev = mock.MagicMock()
    dev.__iter__ = lambda self: iter([])
    dev.read.return_value = b"\x08\x81" + bytes(14)
    d = mod.Device(dev)
    img = fake_jpeg(3000, seed=5)
    assert d.send_image(img) == b"\x08\x81" + bytes(14)
    assert [c.args[:2] for c in dev.write.call_args_list] == [(0x03, p) for p in lcd_frames(img)]
    with pytest.raises(ValueError):
        d.send_image(b"\x89PNG\r\n\x1a\n")


def _t(frame, ts, ep, data, xfer=3):
    return Transfer(frame, ts, 1, 2, ep, xfer, None, data)


def test_png_stream_without_header_and_jpeg_thumbnail():
    # raw PNG files written back to back on a bulk endpoint, no per-packet header
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + (480).to_bytes(4, "big") + (272).to_bytes(4, "big")
    png += bytes(range(1, 200)) * 3 + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    ts, n = [], 0
    for f in range(4):
        for k in range(0, len(png), 256):
            n += 1
            ts.append(_t(n, f + k / 1e4, 0x02, png[k:k + 256]))
    n += 1
    ts.append(_t(n, 10.0, 0x02, b"\x05\x01\x40"))   # a command on the same endpoint stays out of the stream
    [s] = find_streams(ts)
    assert (s["format"], s["header_len"], s["frames"], s["size"], s["ack"]) == ("png", 0, 4, [480, 272], None)
    assert s["packets"] == len(ts) - 1 and s["image_bytes"] == [len(png), len(png)]
    # an EXIF thumbnail (its own SOI/EOI) does not end the outer JPEG early
    inner = fake_jpeg(100, size=32)
    outer = fake_jpeg(300)
    outer = outer[:2] + b"\xff\xe1" + (len(inner) + 2).to_bytes(2, "big") + inner + outer[2:]
    from usb_rea.streams import _ended
    assert _ended("jpeg", outer) == len(outer)
    assert _size("jpeg", fake_jpeg(500, size=320)) == (320, 320)


def test_too_few_frames_is_not_a_stream():
    img = fake_jpeg(600)
    ts = [_t(i + 1, i, 0x01, p) for i, p in enumerate(lcd_frames(img) * 2)]
    assert find_streams(ts) == []
