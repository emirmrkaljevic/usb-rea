"""Image streams whose frames are spread over more than one host->device endpoint."""
import importlib.util
import sys
from unittest import mock

import pytest

from usb_rea.pcap import read_transfers
from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.scaffold import generate
from usb_rea.streams import describe, find_streams
from usb_rea.synth import (UsbmonWriter, device_descriptor, fake_jpeg, gradient, lcd_frames, make_capture,
                           raw888_packets, raw_header)


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


def _spread(layout, n, eps):
    return [eps[k % 2] for k in range(n)] if layout == "alternate" else [eps[k * 2 // n] for k in range(n)]


@pytest.mark.parametrize("layout", ["alternate", "blocks"])
def test_jpeg_frames_over_two_endpoints(tmp_path, layout):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, endpoints=layout)
    proto = analyze(cap)
    assert [(c.name, c.endpoint, c.confidence) for c in proto.commands] == [("brightness", 0x01, 1.0)]
    [s] = proto.streams
    assert (s["format"], s["endpoint"], s["endpoints"], s["endpoint_layout"]) == ("jpeg", 0x03, [0x03, 0x05], layout)
    assert s["header_endpoint"] is None and s["frames"] == 159 and s["size"] == [240, 240]
    assert (s["first_header"], s["next_header"]) == ("08 nn 00 80", "08 ii 00 00")
    assert s["ack"]["endpoint"] == 0x84 and proto.responses == []
    assert "EP 0x03 + 0x05" in describe(s)
    md = render(proto)
    assert "## Image stream on interrupt EP 0x03 + 0x05" in md and "spread over EP 0x03, 0x05" in md

    d, dev = _driver(proto, tmp_path, f"jpeg_{layout}")
    dev.read.return_value = b"\x08\x81" + bytes(14)
    img = fake_jpeg(3000, seed=5)
    d.send_image(img)
    pkts = lcd_frames(img)
    assert [c.args[:2] for c in dev.write.call_args_list] == list(zip(_spread(layout, len(pkts), (0x03, 0x05)), pkts))


@pytest.mark.parametrize("layout", ["alternate", "blocks"])
def test_raw_rgb565_frames_over_two_endpoints(tmp_path, layout):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb565", endpoints=layout)
    proto = analyze(cap)
    assert [(c.name, c.endpoint, c.confidence) for c in proto.commands] == [("brightness", 0x01, 1.0)]
    [s] = proto.streams
    assert (s["format"], s["endpoints"], s["endpoint_layout"], s["header_endpoint"]) == ("rgb565", [0x02, 0x04], layout, None)
    assert (s["size"], s["frames"], s["regions"], s["byteorder"]) == ([160, 128], 79, 20, "little")
    assert s["header_packet"] == "55 aa 02 00 xx xx yy yy ww ww hh hh"
    assert s["ack"]["endpoint"] == 0x82

    d, dev = _driver(proto, tmp_path, f"raw565_{layout}")
    pix = gradient(160, 128, 3)
    d.send_image(pix)
    writes = [c.args[:2] for c in dev.write.call_args_list]
    assert writes[0] == (0x02, raw_header(0, 0, 160, 128))
    parts = [pix[i:i + 512] for i in range(0, len(pix), 512)]
    assert writes[1:] == list(zip(_spread(layout, len(parts), (0x02, 0x04)), parts))


@pytest.mark.parametrize("layout", ["alternate", "blocks"])
def test_raw_rgb888_halves_are_not_two_small_screens(tmp_path, layout):
    # each endpoint alone carries 32768 bytes a frame, which also fits a 128x128 RGB565 screen
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb888", endpoints=layout)
    proto = analyze(cap)
    [s] = proto.streams
    assert (s["format"], s["size"], s["endpoints"], s["endpoint_layout"]) == ("rgb888", [128, 160], [0x02, 0x04], layout)
    assert (s["first_header"], s["next_header"]) == ("00 00 nn nn", "ii ii nn nn")

    d, dev = _driver(proto, tmp_path, f"raw888_{layout}")
    pix = gradient(128, 160, 2, bpp=3)
    d.send_image(pix)
    pkts = raw888_packets(pix)
    assert [c.args[:2] for c in dev.write.call_args_list] == list(zip(_spread(layout, len(pkts), (0x02, 0x04)), pkts))


def test_draw_command_on_the_command_endpoint(tmp_path):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb565", endpoints="command")
    proto = analyze(cap)
    # the draw commands on EP 0x01 go with the pixels, brightness on the same endpoint stays a command
    assert [(c.name, c.endpoint, c.confidence) for c in proto.commands] == [("brightness", 0x01, 1.0)]
    [s] = proto.streams
    assert (s["endpoint"], s["endpoints"], s["endpoint_layout"], s["header_endpoint"]) == (0x02, [0x02], None, 0x01)
    assert s["region"] == {"layout": "xywh", "offset": 4, "endian": "little"}
    assert (s["frames"], s["regions"]) == (79, 20)
    assert "command on EP 0x01" in describe(s)
    assert "The command before each frame goes to EP 0x01, the pixels to EP 0x02" in render(proto)

    d, dev = _driver(proto, tmp_path, "raw565_cmd")
    clock = gradient(48, 16, 7)
    d.send_image(clock, x=100, y=8, size=(48, 16))
    writes = [c.args[:2] for c in dev.write.call_args_list]
    assert writes[0] == (0x01, raw_header(100, 8, 48, 16))
    assert {ep for ep, _ in writes[1:]} == {0x02} and b"".join(p for _, p in writes[1:]) == clock


def test_single_endpoint_streams_say_so(tmp_path):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb565")
    [s] = analyze(cap).streams
    assert (s["endpoints"], s["endpoint_layout"], s["header_endpoint"]) == ([0x02], None, None)


def test_two_screens_on_two_endpoints_stay_two_streams(tmp_path):
    # one device, two screens with their own frame rates: frames never span both endpoints
    w = UsbmonWriter()
    t0 = 1_760_000_000.0
    w.control_in(t0, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    for ep, (wd, ht), fps in ((0x02, (160, 80), 10.0), (0x04, (128, 128), 7.0)):
        t, n = t0 + 0.05 + ep / 100, 0
        while t < t0 + 3.0:
            pix = gradient(wd, ht, n)
            for k in range(0, len(pix), 512):
                w.out(t + 0.0004 * k / 512, ep, pix[k:k + 512], xtype=3)
            t += 1 / fps
            n += 1
    w.save(tmp_path / "two.pcap")
    found = find_streams(read_transfers(tmp_path / "two.pcap"))
    assert sorted((s["endpoints"], s["size"]) for s in found) == [([0x02], [160, 80]), ([0x04], [128, 128])]


def test_endpoints_option_checks(tmp_path):
    with pytest.raises(ValueError):
        make_capture(tmp_path / "x.pcap", device="lcd", image_stream=True, endpoints="command")   # JPEG has no draw command
    with pytest.raises(ValueError):
        make_capture(tmp_path / "x.pcap", device="lcd", endpoints="alternate")
