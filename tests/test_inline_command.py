"""Raw pixel streams whose draw command starts the first pixel packet instead of having its own packet."""
import importlib.util
import json
import sys
from unittest import mock

import pytest

from usb_rea.cli import main
from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.scaffold import generate
from usb_rea.synth import UsbmonWriter, device_descriptor, encode_testcard, gradient, make_capture, raw_header


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
    return mod, dev


def test_rgb565_command_inside_the_first_pixel_packet(tmp_path):
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb565", inline=True)
    proto = analyze(cap)
    # the 12-byte rest of each frame is not taken for a command or a handshake step
    assert [c.name for c in proto.commands] == ["brightness"]
    assert proto.handshake == [] and proto.responses == [] and proto.background == []
    [s] = proto.streams
    plain = analyze(make_capture(tmp_path / "plain.pcap", device="lcd", image_stream=True, raw="rgb565")[0]).streams[0]
    assert (s["format"], s["size"], s["chunk"], s["header_len"]) == ("rgb565", [160, 128], 512, 0)
    assert s["header_inline"] is True and plain["header_inline"] is False
    assert s["header_packet"] == "55 aa 02 00 xx xx yy yy ww ww hh hh"
    assert s["region"] == {"layout": "xywh", "offset": 4, "endian": "little"}
    assert (s["frames"], s["regions"], s["packets"]) == (plain["frames"], plain["regions"], plain["packets"])
    assert s["image_bytes"] == [48 * 16 * 2, 40960] and not s["padded"]
    assert (s["byteorder"], s["ack"]["payload"]) == ("little", "55 aa 82 00")
    md = render(proto)
    assert "plus the command at their start" in md
    assert "Command at the start of each frame's first packet (12 bytes" in md

    mod, dev = _driver(proto, tmp_path, "inline565")
    dev.read.return_value = b"\x55\xaa\x82\x00"
    d = mod.Device(dev)
    pix = gradient(160, 128, 5)
    assert d.send_image(pix) == b"\x55\xaa\x82\x00"
    writes = [c.args[1] for c in dev.write.call_args_list]
    assert b"".join(writes) == raw_header(0, 0, 160, 128) + pix
    assert [len(w) for w in writes] == [512] * 80 + [12]
    dev.write.reset_mock()
    clock = gradient(48, 16, 9)
    d.send_image(clock, x=100, y=8, size=(48, 16))
    writes = [c.args[1] for c in dev.write.call_args_list]
    assert writes[0][:12] == raw_header(100, 8, 48, 16) and b"".join(writes) == raw_header(100, 8, 48, 16) + clock


def _box_header(x, y, w, h, n):
    """A made-up draw command: 5A A5, x0, y0, x1, y1 as u16 big-endian, then the pixel byte count as u32 LE."""
    return b"\x5a\xa5" + b"".join(v.to_bytes(2, "big") for v in (x, y, x + w - 1, y + h - 1)) + n.to_bytes(4, "little")


def _box_capture(path, bgr_card=True):
    w = UsbmonWriter()
    t = 1_760_000_000.0
    w.control_in(t, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    marks, t = [], t + 1.0
    updates = [(0, 0, 240, 240), (16, 16, 64, 32), (0, 0, 240, 240), (0, 0, 240, 240),
               (100, 40, 40, 40), (0, 0, 240, 240), (0, 0, 240, 240)]
    for i, (x, y, wd, ht) in enumerate(updates):
        if bgr_card and (wd, ht) == (240, 240) and i >= 2:
            pix = encode_testcard(240, 240, 3, "bgr")
        else:
            pix = gradient(wd, ht, i, bpp=3)
        data = _box_header(x, y, wd, ht, len(pix)) + pix
        for k in range(0, len(data), 1024):
            w.out(t + 0.0005 * k / 1024, 0x02, data[k:k + 1024])
        t += 0.4
        marks.append({"label": f"brightness {i * 30}", "start": t, "end": t + 0.2})
        w.out(t + 0.05, 0x01, bytes([0xA0, i * 30, 0, 0]))
        t += 0.4
    w.save(path)
    (path.parent / (path.name + ".actions.json")).write_text(json.dumps(marks))
    return path


def test_rgb888_inline_box_command_with_byte_count_and_test_card(tmp_path):
    proto = analyze(_box_capture(tmp_path / "box.pcap"))
    assert [c.name for c in proto.commands] == ["brightness"]
    [s] = proto.streams
    assert (s["format"], s["size"], s["chunk"], s["frames"], s["regions"]) == ("rgb888", [240, 240], 1024, 7, 2)
    assert s["header_inline"] and s["region"] == {"layout": "box", "offset": 2, "endian": "big"}
    assert s["length_field"] == {"offset": 10, "width": 4, "endian": "little"}
    assert s["header_packet"] == "5a a5 xx xx yy yy ex ex ey ey ll ll ll ll"
    # the test card frames are read past the command, so the channel order is found
    assert s["channel_order"] == "bgr" and s["channel_evidence"]["frames_matched"] == 4

    mod, dev = _driver(proto, tmp_path, "inline888")
    d = mod.Device(dev)
    pix = gradient(64, 32, 1, bpp=3)
    d.send_image(pix, x=16, y=16, size=(64, 32))
    writes = [c.args[1] for c in dev.write.call_args_list]
    assert b"".join(writes) == _box_header(16, 16, 64, 32, len(pix)) + pix
    assert all(len(w) == 1024 for w in writes[:-1])


def test_separate_command_packet_still_preferred(tmp_path):
    # the same stream with the command in its own packet keeps the old description
    cap, _ = make_capture(tmp_path / "lcd.pcap", device="lcd", image_stream=True, raw="rgb565")
    [s] = analyze(cap).streams
    assert not s["header_inline"] and s["header_packet"] == "55 aa 02 00 xx xx yy yy ww ww hh hh"
    cap, _ = make_capture(tmp_path / "lcd888.pcap", device="lcd", image_stream=True, raw="rgb888")
    [s] = analyze(cap).streams
    assert not s["header_inline"] and s["header_packet"] is None


def test_synth_and_cli_checks(tmp_path, capsys):
    with pytest.raises(ValueError):
        make_capture(tmp_path / "x.pcap", device="lcd", image_stream=True, raw="rgb888", inline=True)
    with pytest.raises(ValueError):
        make_capture(tmp_path / "x.pcap", device="lcd", image_stream=True, raw="rgb565", inline=True,
                     endpoints="alternate")
    with pytest.raises(SystemExit):
        main(["demo", "--device", "lcd", "--inline", "-o", str(tmp_path / "d")])
    assert main(["demo", "--device", "lcd", "--raw", "rgb565", "--inline", "-o", str(tmp_path / "d")]) == 0
    assert "first packet" in (tmp_path / "d" / "report.md").read_text()
