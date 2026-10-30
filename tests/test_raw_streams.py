"""Raw pixel streams (RGB565 / RGB888 with no image file format) and 16-bit header fields."""
import importlib.util
import json
import sys
from unittest import mock

import pytest

from usb_rea.model import Transfer
from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.scaffold import generate
from usb_rea.streams import _region, _rgb565_order, find_streams
from usb_rea.synth import UsbmonWriter, device_descriptor, gradient, make_capture, raw888_packets, raw_header


def _driver(proto, tmp_path, name="drv"):
    path = tmp_path / f"{name}.py"
    path.write_text(generate(proto))
    usb = mock.MagicMock()
    with mock.patch.dict(sys.modules, {"usb": usb, "usb.core": usb.core}):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    dev = mock.MagicMock()
    dev.__iter__ = lambda self: iter([])
    return mod, dev


def test_rgb565_stream_with_region_command(tmp_path):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb565")
    proto = analyze(cap)
    assert [(c.name, c.endpoint, c.confidence) for c in proto.commands] == [("brightness", 0x01, 1.0)]
    [s] = proto.streams
    assert (s["raw"], s["format"], s["endpoint"], s["xfer_type"], s["chunk"]) == (True, "rgb565", 0x02, 3, 512)
    assert (s["size"], s["frame_bytes"], s["byteorder"], s["fps"]) == ([160, 128], 40960, "little", 10.0)
    assert s["header_packet"] == "55 aa 02 00 xx xx yy yy ww ww hh hh"
    assert s["region"] == {"layout": "xywh", "offset": 4, "endian": "little"}
    assert s["regions"] == 20 and s["header_len"] == 0 and s["partial"] > 0
    assert s["ack"]["endpoint"] == 0x82 and s["ack"]["payload"] == "55 aa 82 00"
    assert proto.responses == [] and proto.background == []
    md = render(proto)
    assert "Raw RGB565 pixels" in md and "Screen: 160x128 RGB565, 40960 bytes" in md
    assert "x, y, width, height as 16-bit little-endian fields from byte 4" in md

    mod, dev = _driver(proto, tmp_path, "lcd565")
    dev.read.return_value = b"\x55\xaa\x82\x00"
    d = mod.Device(dev)
    pix = gradient(160, 128, 3)
    assert d.send_image(pix) == b"\x55\xaa\x82\x00"
    writes = [c.args[1] for c in dev.write.call_args_list]
    assert writes[0] == raw_header(0, 0, 160, 128) and b"".join(writes[1:]) == pix
    assert {len(w) for w in writes[1:]} == {512}
    dev.write.reset_mock()
    clock = gradient(48, 16, 7)
    d.send_image(clock, x=100, y=8, size=(48, 16))
    writes = [c.args[1] for c in dev.write.call_args_list]
    assert writes[0] == raw_header(100, 8, 48, 16) and b"".join(writes[1:]) == clock
    with pytest.raises(ValueError):
        d.send_image(b"\x00" * 100)


def test_pillow_image_is_converted_to_rgb565(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb565")
    mod, dev = _driver(analyze(cap), tmp_path, "lcdpil")
    d = mod.Device(dev)
    img = Image.new("RGB", (160, 128), (255, 0, 0))
    d.send_image(img)
    writes = [c.args[1] for c in dev.write.call_args_list]
    assert b"".join(writes[1:]) == b"\x00\xf8" * (160 * 128)   # pure red, RGB565 little-endian


def test_rgb888_with_16_bit_packet_index_and_count(tmp_path):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb888")
    proto = analyze(cap)
    assert [c.name for c in proto.commands] == ["brightness"]
    [s] = proto.streams
    assert (s["format"], s["size"], s["chunk"], s["header_len"]) == ("rgb888", [128, 160], 64, 4)
    assert (s["first_header"], s["next_header"]) == ("00 00 nn nn", "ii ii nn nn")
    assert (s["count_offset"], s["count_width"], s["count_endian"]) == (2, 2, "little")
    assert (s["index_offset"], s["index_width"], s["index_endian"], s["index_base"]) == (0, 2, "little", 0)
    assert s["size_alternatives"] == ["rgb888 160x128"] and s["header_packet"] is None
    assert "16-bit header fields: packet count little-endian, packet index little-endian" in render(proto)
    mod, dev = _driver(proto, tmp_path, "lcd888")
    d = mod.Device(dev)
    pix = gradient(128, 160, 2, bpp=3)
    assert d.send_image(pix) is None
    assert [c.args[1] for c in dev.write.call_args_list] == raw888_packets(pix)


# ---- Turing Smart Screen (rev A) ground truth ----
# The protocol is documented publicly (e.g. the turing-smart-screen-python project): a USB serial
# device on one bulk OUT endpoint, every command 6 bytes, x, y, end x and end y as four 10-bit fields
# packed big-endian into the first 5 bytes and the command code last; DISPLAY_BITMAP (197) is followed
# by the region's pixels as RGB565 little-endian. The fixture below is written from that description.

def turing_cmd(cmd, x=0, y=0, ex=0, ey=0):
    return (x << 30 | y << 20 | ex << 10 | ey).to_bytes(5, "big") + bytes([cmd])


HELLO, BRIGHTNESS, ORIENTATION, DISPLAY_BITMAP = 69, 110, 121, 197


def _turing_capture(path):
    w = UsbmonWriter()
    t = 1_760_000_000.0
    w.control_in(t, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    w.out(t + 0.1, 0x01, turing_cmd(HELLO, HELLO, HELLO, HELLO, HELLO))
    w.out(t + 0.2, 0x01, turing_cmd(ORIENTATION))
    full = gradient(320, 480)
    marks, t = [], t + 1.0
    updates = [(0, 0, 320, 480), (10, 200, 100, 20), (0, 0, 320, 480), (60, 300, 200, 40),
               (0, 0, 320, 480), (10, 200, 100, 20), (0, 0, 320, 480)]
    levels = [0, 64, 128, 252]
    for i, (x, y, wd, ht) in enumerate(updates):
        pix = full if (wd, ht) == (320, 480) else gradient(wd, ht, i)
        w.out(t, 0x01, turing_cmd(DISPLAY_BITMAP, x, y, x + wd - 1, y + ht - 1))
        for k in range(0, len(pix), 4096):
            w.out(t + 0.001 + 0.004 * k / 4096, 0x01, pix[k:k + 4096])
        t += 0.5
        if i < len(levels):
            marks.append({"label": f"brightness {levels[i]}", "start": t, "end": t + 0.3})
            w.out(t + 0.1, 0x01, turing_cmd(BRIGHTNESS, levels[i]))
            t += 0.5
    w.save(path)
    (path.parent / (path.name + ".actions.json")).write_text(json.dumps(marks))
    return path


def test_turing_smart_screen_rev_a(tmp_path):
    cap = _turing_capture(tmp_path / "turing.pcap")
    proto = analyze(cap)
    [s] = proto.streams
    assert (s["format"], s["endpoint"], s["frames"], s["regions"]) == ("rgb565", 0x01, 7, 3)
    assert (s["size"], s["byteorder"], s["chunk"]) == ([320, 480], "little", 4096)
    assert s["header_packet"] == "rr rr rr rr rr c5"
    assert s["region"] == {"layout": "box10", "offset": 0, "endian": "big"}
    # the hello, orientation and brightness commands on the same endpoint stay commands
    assert [c.name for c in proto.commands] == ["brightness"]
    mod, dev = _driver(proto, tmp_path, "turing")
    d = mod.Device(dev)
    d.send_image(gradient(100, 20), x=10, y=200, size=(100, 20))
    writes = [c.args[1] for c in dev.write.call_args_list]
    # open() first replays the hello and orientation commands the app sent before any action
    assert writes[:2] == [turing_cmd(HELLO, HELLO, HELLO, HELLO, HELLO), turing_cmd(ORIENTATION)]
    assert writes[2:] == [turing_cmd(DISPLAY_BITMAP, 10, 200, 109, 219), gradient(100, 20)]


def _t(frame, ts, ep, data, xfer=3):
    return Transfer(frame, ts, 1, 2, ep, xfer, None, data)


def test_one_transfer_per_frame_back_to_back():
    # one 115200-byte URB per 240x240 RGB565 frame, no command and no pause between frames
    pix = gradient(240, 240)
    ts = [_t(i + 1, i * 0.01, 0x02, pix) for i in range(6)]
    [s] = find_streams(ts)
    assert (s["format"], s["size"], s["frames"], s["packets"]) == ("rgb565", [240, 240], 6, 6)


def test_no_raw_stream_for_firmware_or_short_commands():
    # a firmware download: large chunks, but the totals are no screen size and never repeat
    ts, n, t = [], 0, 0.0
    for block in (70000, 91000, 33333):
        for k in range(0, block, 1024):
            n += 1
            ts.append(_t(n, t, 0x02, bytes(min(1024, block - k))))
            t += 0.001
        t += 1.0
    ts += [_t(n + 1 + i, t + i, 0x01, bytes([0xAA, i, 0, 0, 0])) for i in range(10)]
    assert find_streams(ts) == []
    # two screen-sized frames are not enough
    pix = gradient(128, 128)
    assert find_streams([_t(i + 1, i, 0x02, pix) for i in range(2)]) == []


def test_helpers():
    assert _region("box10", turing_cmd(197, 0, 0, 319, 479), 0, "big") == (0, 0, 320, 480)
    assert turing_cmd(197, 0, 0, 319, 479).hex(" ") == "00 00 04 fd df c5"
    assert _rgb565_order(gradient(64, 8, order="big")) == "big"
    assert _rgb565_order(bytes(512)) is None
