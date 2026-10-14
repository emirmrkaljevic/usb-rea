"""HID report descriptor decoder, checked against the descriptors printed in the HID 1.11 spec."""
import json

import pytest

from usb_rea import hid
from usb_rea.cli import main
from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.synth import make_capture, LAMP_HID_DESCRIPTOR

# HID 1.11 Appendix E.10, boot mouse
MOUSE = ("05 01 09 02 A1 01 09 01 A1 00 05 09 19 01 29 03 15 00 25 01 95 03 75 01 81 02 95 01 75 05 81 01"
         " 05 01 09 30 09 31 15 81 25 7F 75 08 95 02 81 06 C0 C0")
# HID 1.11 Appendix E.6, boot keyboard
KEYBOARD = ("05 01 09 06 A1 01 05 07 19 E0 29 E7 15 00 25 01 75 01 95 08 81 02 95 01 75 08 81 01"
            " 95 05 75 01 05 08 19 01 29 05 91 02 95 01 75 03 91 01"
            " 95 06 75 08 15 00 25 65 05 07 19 00 29 65 81 00 C0")
# Constructed in the style of Logitech HID++ (documented: short report 0x10 = 7 bytes, long 0x11 = 20 bytes)
HIDPP = ("06 00 FF 09 01 A1 01 85 10 75 08 95 06 15 00 26 FF 00 09 01 81 00 09 01 91 00 C0"
         " 06 00 FF 09 02 A1 01 85 11 75 08 95 13 15 00 26 FF 00 09 02 81 00 09 02 91 00 C0")


def test_boot_mouse_layout_and_decode():
    d = hid.parse(MOUSE)
    assert d.top_usages == ["Generic Desktop: Mouse"]
    (inp,) = d.reports
    assert (inp.report_type, inp.report_id, inp.length) == ("Input", 0, 3)
    buttons, pad, xy = inp.fields
    assert (buttons.bit_offset, buttons.size, buttons.count, buttons.usages) == (0, 1, 3, [1, 2, 3])
    assert pad.constant and pad.bit_offset == 3
    assert (xy.bit_offset, xy.logical_min, xy.logical_max, xy.relative) == (8, -127, 127, True)
    assert hid.decode(d, "Input", bytes([0x05, 0xFE, 0x03])) == [
        ("Button: Button 1", 1), ("Button: Button 2", 0), ("Button: Button 3", 1),
        ("Generic Desktop: X", -2), ("Generic Desktop: Y", 3)]


def test_boot_keyboard_has_8_byte_input_and_led_output():
    d = hid.parse(KEYBOARD)
    assert d.report("Input").length == 8
    out = d.report("Output")
    assert out.length == 1
    leds = out.fields[0]
    assert hid.usage_name(leds.usage_page, leds.usages[1]) == "Caps Lock"
    keys = hid.decode(d, "Input", bytes([0x02, 0, 0x04, 0, 0, 0, 0, 0]))
    assert ("Keyboard/Keypad: 0xE1", 1) in keys       # left shift modifier
    assert ("Keyboard/Keypad usage", 0x04) in keys    # 'a' in the key array
    assert hid.decode(d, "Output", bytes([0x02]))[1] == ("LED: Caps Lock", 1)


def test_report_ids_and_vendor_pages():
    d = hid.parse(HIDPP)
    assert d.uses_report_ids
    assert d.report("Output", 0x10).length == 7
    assert d.report("Output", 0x11).length == 20
    assert d.report("Output", 0x11).vendor
    rep = hid.match(d, None, 0x02, bytes.fromhex("10ff0d1d000000"))
    assert rep is d.report("Output", 0x10)
    setup = bytes([0x21, 0x09, 0x11, 0x02, 2, 0, 20, 0])  # SET_REPORT(Output, id 0x11)
    assert hid.match(d, setup, 0, b"") is d.report("Output", 0x11)


def test_push_pop_long_usage_and_errors():
    # Push, change page via 4-byte usage, Pop restores report size
    d = hid.parse("05 01 09 05 A1 01 75 08 95 01 A4 75 10 0B 30 00 01 00 81 02 B4 0B 31 00 01 00 81 02 C0")
    f1, f2 = d.report("Input").fields
    assert (f1.size, f1.usage_page, f1.usages) == (16, 0x01, [0x30])
    assert (f2.size, f2.bit_offset) == (8, 16)
    with pytest.raises(ValueError):
        hid.parse("05")          # truncated item
    assert hid.items(bytes.fromhex("fe 02 10 aa bb"))[0].kind == "long"


def test_capture_with_hid_descriptor_is_annotated(tmp_path):
    cap, _ = make_capture(tmp_path / "lamp.pcap", transport="control")
    proto = analyze(cap)
    (h,) = proto.hid
    assert bytes.fromhex(h["descriptor"]) == LAMP_HID_DESCRIPTOR
    assert set(h["commands"]) == {c.name for c in proto.commands}
    assert all("Output report (no id, 5 bytes, Vendor 0xFF00)" == v for v in h["commands"].values())
    md = render(proto, str(cap))
    assert "## HID report descriptor, interface 0" in md and "- HID: Output report" in md
    json.dumps(proto.to_dict(), default=str)


def test_bulk_capture_has_no_hid_section(tmp_path):
    cap, _ = make_capture(tmp_path / "lamp.pcap")
    assert analyze(cap).hid == []


def test_cli_hid(tmp_path, capsys):
    assert main(["hid", MOUSE, "--decode", "01 0a f6"]) == 0
    out = capsys.readouterr().out
    assert "Generic Desktop: X = 10" in out and "Generic Desktop: Y = -10" in out
    cap, _ = make_capture(tmp_path / "lamp.pcap", transport="control")
    assert main(["hid", str(cap), "--items"]) == 0
    assert "Output (Data,Var,Abs)" in capsys.readouterr().out
    cap2, _ = make_capture(tmp_path / "bulk.pcap")
    assert main(["hid", str(cap2)]) == 1
