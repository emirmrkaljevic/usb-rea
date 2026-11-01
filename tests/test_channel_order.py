"""RGB or BGR (and RGB565 byte order) settled by frames that show the usb-rea test card."""
import importlib.util
import sys
import zlib
from unittest import mock

import pytest

from usb_rea.cli import main
from usb_rea.model import Transfer
from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.scaffold import generate
from usb_rea.streams import _channel_order, _is_testcard, _readings, write_testcard
from usb_rea.streams import testcard as card
from usb_rea.synth import encode_testcard, gradient, make_capture


def _driver(proto, tmp_path, name):
    path = tmp_path / f"{name}.py"
    path.write_text(generate(proto))
    usb = mock.MagicMock()
    with mock.patch.dict(sys.modules, {"usb": usb, "usb.core": usb.core}):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    dev = mock.MagicMock()
    dev.__iter__ = lambda self: iter([])
    return mod.Device(dev), dev


def _matches(fmt, pix):
    return [r for r in _readings(fmt) if _is_testcard(fmt, pix, *r, 2048)]


@pytest.mark.parametrize("order", ["rgb", "bgr"])
def test_rgb888_channel_order_from_test_card_frames(tmp_path, order):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb888", testcard=order)
    proto = analyze(cap)
    assert [c.name for c in proto.commands] == ["brightness"]
    [s] = proto.streams
    assert s["format"] == "rgb888" and s["channel_order"] == order
    ev = s["channel_evidence"]
    assert (ev["method"], ev["frames_matched"], ev["agree"], ev["confidence"]) == ("testcard", 6, 6, 1.0)
    assert ev["byteorder"] is None and len(ev["frames"]) == 5
    assert f"Channel order: {order.upper()} (the usb-rea test card shows in 6 of 39 full frames checked" in render(proto)


def test_bgr565_from_test_card_and_driver_swaps_red_and_blue(tmp_path):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb565", testcard="bgr")
    proto = analyze(cap)
    [s] = proto.streams
    assert (s["channel_order"], s["byteorder"], s["regions"]) == ("bgr", "little", 20)
    assert s["channel_evidence"]["frames_matched"] == 6   # the clock redraws are not full frames
    md = render(proto)
    assert "little-endian (the test card frames only read right that way)" in md
    Image = pytest.importorskip("PIL.Image")
    d, dev = _driver(proto, tmp_path, "bgr565")
    d.send_image(Image.new("RGB", (160, 128), (255, 0, 0)))
    writes = [c.args[1] for c in dev.write.call_args_list]
    assert b"".join(writes[1:]) == b"\x1f\x00" * (160 * 128)   # red lands in the low 5 bits


def test_bgr888_driver_sends_blue_first(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb888", testcard="bgr")
    d, dev = _driver(analyze(cap), tmp_path, "bgr888")
    d.send_image(Image.new("RGB", (128, 160), (255, 128, 0)))
    pix = b"".join(c.args[1][4:] for c in dev.write.call_args_list)
    assert pix == bytes((0, 128, 255)) * (128 * 160)


def test_without_test_card_the_order_is_unknown(tmp_path):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb565")
    proto = analyze(cap)
    [s] = proto.streams
    assert s["channel_order"] is None and s["channel_evidence"] is None
    assert "Channel order: unknown (pixels alone do not tell RGB from BGR); send_image() assumes RGB" in render(proto)


def test_one_reading_only_also_rotated_mirrored_and_big_endian():
    w, h = 96, 64
    assert _matches("rgb888", card(w, h)) == [("rgb", None)]
    assert _matches("rgb888", encode_testcard(w, h, 3, "bgr")) == [("bgr", None)]
    for order in ("rgb", "bgr"):
        for endian in ("little", "big"):
            assert _matches("rgb565", encode_testcard(w, h, 2, order, endian)) == [(order, endian)]
    # the app rotated the card 90 degrees and mirrored it: same colour shares
    rgb = card(w, h)
    px = [rgb[i:i + 3] for i in range(0, len(rgb), 3)]
    turned = [px[y * w + x] for x in range(w) for y in range(h)]
    assert _matches("rgb888", b"".join(turned)) == [("rgb", None)]
    assert _matches("rgb888", b"".join(turned[::-1])) == [("rgb", None)]
    assert _matches("rgb888", gradient(w, h, bpp=3)) == []
    assert _matches("rgb565", gradient(w, h)) == []


def test_disagreeing_frames_stay_unknown():
    def frame(n, pix):
        return [Transfer(n, float(n), 1, 2, 0x02, 3, None, pix[i:i + 512]) for i in range(0, len(pix), 512)]
    frames = [frame(1, encode_testcard(64, 64, 3, "rgb")), frame(2, encode_testcard(64, 64, 3, "bgr"))]
    out = _channel_order(frames, 0, "rgb888", 64 * 64 * 3, None)
    assert out["channel_order"] is None
    assert out["channel_evidence"]["confidence"] == 0.5 and out["channel_evidence"]["frames_matched"] == 2


def test_testcard_png(tmp_path, capsys):
    out = tmp_path / "card.png"
    assert main(["testcard", "-o", str(out), "--size", "40x20"]) == 0
    assert "40x20" in capsys.readouterr().out
    data = out.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n") and data[16:24] == (40).to_bytes(4, "big") + (20).to_bytes(4, "big")
    idat = data[data.index(b"IDAT") + 4:data.index(b"IEND") - 8]
    rows = zlib.decompress(idat)
    assert len(rows) == 20 * (1 + 40 * 3)
    assert rows[1:4] == b"\xff\x00\x00" and rows[1 + 39 * 3:1 + 40 * 3] == b"\x00\xff\x00"
    write_testcard(tmp_path / "small.png", 8, 8)
    with pytest.raises(SystemExit):
        main(["testcard", "-o", str(out), "--size", "huge"])
