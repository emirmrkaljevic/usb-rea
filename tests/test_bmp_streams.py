"""BMP image streams: detected like JPEG/PNG/GIF, with bfSize frame length and BITMAPINFOHEADER size."""
import importlib.util
import sys
from unittest import mock

import pytest

from usb_rea.cli import main
from usb_rea.model import Transfer
from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.scaffold import generate
from usb_rea.streams import _ended, _size, find_streams
from usb_rea.synth import fake_bmp, lcd_frames, make_capture


def _t(frame, ts, ep, data, xfer=3):
    return Transfer(frame, ts, 1, 2, ep, xfer, None, data)


def test_synth_bmp_stream_found(tmp_path):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, bmp=True)
    proto = analyze(cap)
    assert [c.name for c in proto.commands] == ["brightness"]
    [s] = proto.streams
    assert (s["endpoint"], s["xfer_type"], s["format"], s["chunk"], s["padded"]) == (0x03, 1, "bmp", 512, True)
    assert (s["header_len"], s["first_header"], s["next_header"]) == (4, "08 nn 00 80", "08 ii 00 00")
    assert s["size"] == [64, 64] and s["frames"] >= 3 and s["fps"] == 20.0
    assert s["image_bytes"] is not None and s["image_bytes"][0] >= 1500
    assert s["ack"]["endpoint"] == 0x84
    md = render(proto)
    assert "BMP images sent continuously" in md and "Image size: 64x64" in md


def test_driver_send_image_bmp(tmp_path):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, bmp=True)
    proto = analyze(cap)
    src = generate(proto)
    path = tmp_path / "lcd_driver.py"
    path.write_text(src)
    usb = mock.MagicMock()
    with mock.patch.dict(sys.modules, {"usb": usb, "usb.core": usb.core}):
        spec = importlib.util.spec_from_file_location("lcd_bmp_driver", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    dev = mock.MagicMock()
    dev.__iter__ = lambda self: iter([])
    dev.read.return_value = b"\x08\x81" + bytes(14)
    d = mod.Device(dev)
    img = fake_bmp(3000, seed=5)
    assert d.send_image(img) == b"\x08\x81" + bytes(14)
    assert [c.args[:2] for c in dev.write.call_args_list] == [(0x03, p) for p in lcd_frames(img)]
    with pytest.raises(ValueError):
        d.send_image(b"\xff\xd8\xff\xe0")


def test_bmp_with_usb_header_offset():
    # short per-packet header before BM, like JPEG streams with a header
    img = fake_bmp(1800, size=80, seed=3)
    assert _size("bmp", img) == (80, 80)
    assert _ended("bmp", img) == len(img)
    assert _ended("bmp", img[:40]) is None
    ts, n = [], 0
    for f in range(4):
        for k, pkt in enumerate(lcd_frames(img, chunk=256)):
            n += 1
            ts.append(_t(n, f + k / 1e4, 0x02, pkt, xfer=3))
    [s] = find_streams(ts)
    assert (s["format"], s["header_len"], s["frames"], s["size"]) == ("bmp", 4, 4, [80, 80])
    assert s["image_bytes"] == [len(img), len(img)]


def test_bmp_top_down_height_and_no_header():
    # top-down BMP (negative biHeight) and raw BM files with no per-packet header
    img = fake_bmp(1200, size=64, seed=1, top_down=True)
    assert _size("bmp", img) == (64, 64)
    ts, n = [], 0
    for f in range(3):
        for k in range(0, len(img), 256):
            n += 1
            ts.append(_t(n, f + k / 1e4, 0x02, img[k:k + 256]))
    [s] = find_streams(ts)
    assert (s["format"], s["header_len"], s["frames"], s["size"]) == ("bmp", 0, 3, [64, 64])


def test_jpeg_still_default_and_bmp_flag_checks(tmp_path):
    cap, _ = make_capture(tmp_path / "jpeg.pcap", device="lcd", image_stream=True)
    assert analyze(cap).streams[0]["format"] == "jpeg"
    with pytest.raises(ValueError):
        make_capture(tmp_path / "x.pcap", device="lcd", image_stream=True, bmp=True, raw="rgb565")
    with pytest.raises(ValueError):
        make_capture(tmp_path / "x.pcap", device="fan", image_stream=True, bmp=True)
    assert main(["demo", "--device", "lcd", "--bmp", "-o", str(tmp_path / "d")]) == 0
    assert (tmp_path / "d" / "report.md").read_text().count("BMP") >= 1
