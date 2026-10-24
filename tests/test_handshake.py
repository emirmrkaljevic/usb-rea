"""Handshake: messages sent once before the first action, session tokens, and the driver's open()."""
import importlib.util
import json
from unittest import mock

import pytest

from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.scaffold import generate
from usb_rea.synth import UsbmonWriter, device_descriptor, fan_handshake, make_capture

T0 = 1_760_000_000.0


def _driver(tmp_path, proto, name):
    path = tmp_path / f"{name}.py"
    path.write_text(generate(proto))
    spec = importlib.util.spec_from_file_location(name, path)
    drv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drv)
    return drv


def _fake(replies):
    sent = []
    fake = mock.MagicMock()
    fake.__iter__.return_value = []
    fake.write.side_effect = lambda ep, data: sent.append((ep, bytes(data))) or len(data)
    fake.read.side_effect = list(replies)
    return fake, sent


@pytest.mark.parametrize("kw", [{}, {"poll": 0.5, "observe": True}, {"poll": 0.25, "transport": "control"}])
def test_fan_handshake_found(tmp_path, kw):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", handshake=True, **kw)
    p = analyze(cap)
    hs = p.handshake
    assert [s["request"][:8] for s in hs] == ["5a 00 01", "5a 00 02", "5a 00 03"]   # polls are not in it
    assert [s["expect"] for s in hs] == ["a5 01 ?? ?? ?? ?? ??", "a5 02 01 ??", "a5 03 01 ??"]
    assert hs[0]["tokens"] == [{"reply_offset": 2, "width": 4, "used_by": [{"step": 2, "offset": 3}]}]
    assert hs[1]["uses"] == [{"step": 1, "reply_offset": 2, "offset": 3, "width": 4}]
    assert all(s["request_checksum"]["algo"] == "crc16_modbus" for s in hs)
    assert all(s["reply_checksum"]["algo"] == "sum8" for s in hs)
    assert [c.name for c in p.commands] == ["fan", "color", "mode"]     # the actions are unchanged
    if kw.get("observe"):
        assert all(o["matched"] for o in p.observations)


def test_no_handshake_without_session_setup(tmp_path):
    assert analyze(make_capture(tmp_path / "fan.pcap", device="fan", poll=0.5)[0]).handshake == []
    assert analyze(make_capture(tmp_path / "lamp.pcap")[0]).handshake == []


def test_report_and_json(tmp_path):
    p = analyze(make_capture(tmp_path / "fan.pcap", device="fan", handshake=True)[0])
    md = render(p)
    assert "## Handshake (sent once, before the first action)" in md
    assert "| 2 | bulk EP 0x01 | `5a 00 02" in md and "Step 2 request bytes 3-6 repeat bytes 2-5" in md
    d = json.loads(json.dumps(p.to_dict(), default=str))
    assert len(d["handshake"]) == 3 and d["handshake"][1]["uses"][0]["offset"] == 3


def test_message_sent_again_later_is_not_handshake(tmp_path):
    """A query sent before the first click and again during the session is not session setup."""
    w = UsbmonWriter()
    w.control_in(T0, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    w.out(T0 + 0.1, 0x01, bytes([0x10, 0x01, 0x02, 0x03]))          # hello, once
    w.in_(T0 + 0.105, 0x81, bytes([0x90, 0x00]))
    w.out(T0 + 0.2, 0x01, bytes([0x20, 0x00, 0x00, 0x00]))          # status, also sent later
    marks = []
    for i, v in enumerate((10, 20, 30, 40)):
        t = T0 + 1 + i
        w.out(t + 0.3, 0x01, bytes([0x30, v, 0x00, 0x00]))
        if i == 2:
            w.out(t + 0.6, 0x01, bytes([0x20, 0x00, 0x00, 0x00]))
        marks.append({"label": f"level {v}", "start": t, "end": t + 0.9})
    cap = tmp_path / "x.pcap"
    w.save(cap)
    (tmp_path / "x.pcap.actions.json").write_text(json.dumps(marks))
    hs = analyze(cap).handshake
    assert [s["request"] for s in hs] == ["10 01 02 03"] and hs[0]["reply"] == "90 00"
    assert hs[0]["request_checksum"] is None and hs[0]["expect"] == "90 00"


def _token_capture(path):
    """open: 01 00 00 00 -> 81 <token 4> ; every command 02 <token 4> <level>."""
    w = UsbmonWriter()
    w.control_in(T0, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    token = bytes([0x12, 0x34, 0x56, 0x78])
    w.out(T0 + 0.1, 0x01, bytes([0x01, 0, 0, 0]))
    w.in_(T0 + 0.103, 0x81, b"\x81" + token)
    marks = []
    for i, v in enumerate((10, 20, 30, 40)):
        t = T0 + 1 + i
        w.out(t + 0.3, 0x01, b"\x02" + token + bytes([v]))
        marks.append({"label": f"level {v}", "start": t, "end": t + 0.9})
    w.save(path)
    path.with_suffix(".pcap.actions.json").write_text(json.dumps(marks))
    return path


def test_token_reused_by_commands(tmp_path):
    p = analyze(_token_capture(tmp_path / "tok.pcap"))
    hs = p.handshake
    assert hs[0]["tokens"] == [{"reply_offset": 1, "width": 4,
                                "used_by": [{"command": "level", "packet": 0, "offset": 1}]}]
    assert hs[0]["expect"] == "81 ?? ?? ?? ??"
    assert any("session token" in n for n in p.commands[0].notes)
    assert "Command `level` bytes 1-4 repeat bytes 1-4 of the reply to step 1" in render(p)
    # the driver opens the session and uses this session's token in every command
    drv = _driver(tmp_path, p, "drv_tok")
    fake, sent = _fake([b"\x81\xaa\xbb\xcc\xdd"])
    d = drv.Device(fake)
    d.set_level(50)
    assert sent == [(1, bytes([1, 0, 0, 0])), (1, bytes([2, 0xAA, 0xBB, 0xCC, 0xDD, 50]))]
    fake, _ = _fake([b"\x82\xaa\xbb\xcc\xdd"])              # fixed byte differs
    with pytest.raises(RuntimeError, match="handshake step 1"):
        drv.Device(fake)
    fake, sent = _fake([])
    drv.Device(fake, handshake=False).set_level(5)          # opt out: nothing is replayed
    assert sent == [(1, bytes([2, 0x12, 0x34, 0x56, 0x78, 5]))]


def test_driver_replays_fan_handshake(tmp_path):
    p = analyze(make_capture(tmp_path / "fan.pcap", device="fan", handshake=True)[0])
    drv = _driver(tmp_path, p, "drv_fan_hs")
    token = bytes([0x01, 0x02, 0x03, 0x04])                 # a new session gets a new token
    replies = [r for _, r in fan_handshake(token)]
    fake, sent = _fake(replies)
    d = drv.Device(fake)
    assert [s for _, s in sent] == [q for q, _ in fan_handshake(token)]   # token copied, CRC recomputed
    assert d.session == replies
    bad = bytearray(replies[1])
    bad[-1] ^= 0xFF                                          # reply checksum broken
    fake, _ = _fake([replies[0], bytes(bad), replies[2]])
    with pytest.raises(RuntimeError, match="handshake step 2"):
        drv.Device(fake)
    fake, sent = _fake([replies[0], bytes(bad), replies[2]])
    drv.Device(fake, handshake=False).open(check=False)
    assert len(sent) == 3


def test_handshake_rejects_other_devices(tmp_path):
    with pytest.raises(ValueError):
        make_capture(tmp_path / "lamp.pcap", handshake=True)


def test_cli_demo_fan_shows_handshake(tmp_path, capsys):
    from usb_rea.cli import main
    assert main(["demo", "--device", "fan", "-o", str(tmp_path / "d")]) == 0
    out = capsys.readouterr().out
    assert "handshake (3 messages" in out and "bytes 3-6 = token from step 1" in out
    assert "HANDSHAKE = [{" in (tmp_path / "d" / "fan_driver.py").read_text()
