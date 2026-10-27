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
    assert "reply byte 2 = 01 (2x, most common): the steps below" in out
    assert "reply byte 2 = 02 (1x): 5a 00 04 01" in out
    assert "HANDSHAKE = [{" in (tmp_path / "d" / "fan_driver.py").read_text()


def _retry_capture(path):
    """hello sent twice (first copy unanswered), auth answered 'busy' once and resent, then commands."""
    w = UsbmonWriter()
    w.control_in(T0, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    token = bytes([0x12, 0x34, 0x56, 0x78])
    w.out(T0 + 0.1, 0x01, bytes([0x01, 0, 0, 0]))                  # hello, no reply
    w.out(T0 + 0.35, 0x01, bytes([0x01, 0, 0, 0]))                 # hello again
    w.in_(T0 + 0.353, 0x81, b"\x81" + token)
    w.out(T0 + 0.4, 0x01, b"\x03" + token)                         # auth
    w.in_(T0 + 0.403, 0x81, bytes([0xE0, 0x01]))                   # busy
    w.out(T0 + 0.5, 0x01, b"\x03" + token)                         # auth again
    w.in_(T0 + 0.503, 0x81, bytes([0x83, 0x00]))
    marks = []
    for i, v in enumerate((10, 20, 30, 40)):
        t = T0 + 1 + i
        w.out(t + 0.3, 0x01, b"\x02" + token + bytes([v]))
        marks.append({"label": f"level {v}", "start": t, "end": t + 0.9})
    w.save(path)
    path.with_suffix(".pcap.actions.json").write_text(json.dumps(marks))
    return path


def test_retries_are_one_step(tmp_path):
    p = analyze(_retry_capture(tmp_path / "retry.pcap"))
    hs = p.handshake
    assert [s["request"] for s in hs] == ["01 00 00 00", "03 12 34 56 78"]
    assert [len(s["retries"]) for s in hs] == [1, 1]
    assert hs[0]["retries"][0]["reply"] is None and hs[1]["retries"][0]["reply"] == "e0 01"
    assert hs[0]["reply"] == "81 12 34 56 78" and hs[1]["reply"] == "83 00"
    assert hs[1]["uses"] == [{"step": 1, "reply_offset": 1, "offset": 1, "width": 4}]
    assert "Step 1 was sent 2 times in a row" in render(p)


def test_driver_retries_a_step(tmp_path):
    import usb.core
    p = analyze(_retry_capture(tmp_path / "retry.pcap"))
    drv = _driver(tmp_path, p, "drv_retry")
    tok = b"\xaa\xbb\xcc\xdd"
    # hello times out once, auth answers busy once: both are resent, the token is this session's
    fake, sent = _fake([usb.core.USBError("timeout"), b"\x81" + tok, b"\xe0\x01", b"\x83\x00"])
    d = drv.Device(fake)
    assert [s for _, s in sent] == [bytes([1, 0, 0, 0])] * 2 + [b"\x03" + tok] * 2
    assert d.session == [b"\x81" + tok, b"\x83\x00"]
    fake, _ = _fake([b"\x81" + tok, b"\xe0\x01", b"\xe0\x01"])     # still busy after the app's retries
    with pytest.raises(RuntimeError, match="handshake step 2"):
        drv.Device(fake)


@pytest.mark.parametrize("kw", [{}, {"poll": 0.5, "observe": True}, {"poll": 0.25, "transport": "control"}])
def test_handshake_sent_again_is_a_reopen(tmp_path, kw):
    """The app opens the session again halfway (new token): still the handshake, not part of an action."""
    base = analyze(make_capture(tmp_path / "a.pcap", device="fan", handshake=True, **kw)[0])
    p = analyze(make_capture(tmp_path / "b.pcap", device="fan", handshake=True, reopen=True, **kw)[0])
    assert [s["request"][:8] for s in p.handshake] == ["5a 00 01", "5a 00 02", "5a 00 03"]
    assert [len(s["reopens"]) for s in p.handshake] == [1, 1, 1]
    assert [s["expect"] for s in p.handshake] == [s["expect"] for s in base.handshake]
    assert [(c.name, [f.describe() for f in c.fields]) for c in p.commands] == \
        [(c.name, [f.describe() for f in c.fields]) for c in base.commands]
    assert "sent the whole handshake again later" in render(p)
    json.dumps(p.to_dict(), default=str)


def test_partial_repeat_is_not_a_reopen(tmp_path):
    """Only the hello sent again later (no auth, no start): not a reopen, so hello is not a handshake step."""
    w = UsbmonWriter()
    w.control_in(T0, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    w.out(T0 + 0.1, 0x01, bytes([0x10, 0x01, 0x02, 0x03]))
    w.in_(T0 + 0.105, 0x81, bytes([0x90, 0x00]))
    w.out(T0 + 0.2, 0x01, bytes([0x11, 0x00, 0x00, 0x00]))
    w.in_(T0 + 0.205, 0x81, bytes([0x91, 0x00]))
    marks = []
    for i, v in enumerate((10, 20, 30, 40)):
        t = T0 + 1 + i
        w.out(t + 0.3, 0x01, bytes([0x30, v, 0x00, 0x00]))
        if i == 2:
            w.out(t + 0.6, 0x01, bytes([0x10, 0x01, 0x02, 0x03]))
        marks.append({"label": f"level {v}", "start": t, "end": t + 0.9})
    cap = tmp_path / "x.pcap"
    w.save(cap)
    (tmp_path / "x.pcap.actions.json").write_text(json.dumps(marks))
    hs = analyze(cap).handshake
    assert [s["request"] for s in hs] == ["11 00 00 00"] and hs[0]["reopens"] == []


@pytest.mark.parametrize("kw", [{}, {"poll": 0.5, "observe": True}, {"poll": 0.25, "transport": "control"}])
def test_branch_on_reply_byte(tmp_path, kw):
    """auth answered 'needs calibration' (02) in one reopened session: the app sent calibrate before start."""
    base = analyze(make_capture(tmp_path / "a.pcap", device="fan", handshake=True, **kw)[0])
    p = analyze(make_capture(tmp_path / "b.pcap", device="fan", handshake=True, branch=True, **kw)[0])
    hs = p.handshake
    assert [s["request"][:8] for s in hs] == ["5a 00 01", "5a 00 02", "5a 00 03"]
    assert [len(s["reopens"]) for s in hs] == [2, 2, 1]       # start was only sent again in the 01 session
    assert hs[1]["expect"] == "a5 02 ?? ??" and "branches" not in hs[0] and "branches" not in hs[2]
    br = hs[1]["branches"]
    assert br["offset"] == 2 and br["default"] == "01" and list(br["cases"]) == ["01", "02"]
    assert br["cases"]["01"]["main"] and br["cases"]["01"]["count"] == 2
    two = br["cases"]["02"]
    assert two["count"] == 1 and not two["main"]
    assert [(x["step"], x["request"][:11], x["expect"]) for x in two["steps"]] == \
        [(3, "5a 00 04 01", "a5 04 01 ??"), (4, "5a 00 03 01", "a5 03 01 ??")]
    assert all(x["request_checksum"]["algo"] == "crc16_modbus" for x in two["steps"])
    assert [(c.name, [f.describe() for f in c.fields]) for c in p.commands] == \
        [(c.name, [f.describe() for f in c.fields]) for c in base.commands]   # branch messages are not actions
    md = render(p)
    assert "Step 2 branches on reply byte 2" in md and "falls back to the most common one (`01`)" in md
    json.dumps(p.to_dict(), default=str)


def test_driver_takes_the_branch(tmp_path):
    p = analyze(make_capture(tmp_path / "fan.pcap", device="fan", handshake=True, branch=True)[0])
    src = generate(p)
    assert "# step 2 branches on reply byte 2 (values 0x01, 0x02)" in src and "most common branch, 0x01" in src
    drv = _driver(tmp_path, p, "drv_branch")
    token = bytes([0x01, 0x02, 0x03, 0x04])
    for status in (0x01, 0x02):
        pairs = fan_handshake(token, status)
        fake, sent = _fake([r for _, r in pairs])
        d = drv.Device(fake)
        assert [s for _, s in sent] == [q for q, _ in pairs]      # calibrate only when the fan asked for it
        assert d.branches == {2: status} and len(d.session) == len(pairs)
    # a status the capture never showed: the most common branch (01, straight to start)
    pairs = fan_handshake(token)
    auth = bytearray(pairs[1][1])
    auth[2], auth[3] = 0x07, (auth[3] + 6) & 0xFF                 # keep the sum8 valid
    fake, sent = _fake([pairs[0][1], bytes(auth), pairs[2][1]])
    d = drv.Device(fake)
    assert [s for _, s in sent] == [q for q, _ in pairs] and d.branches == {2: 0x01}


def _branch_capture(path, second: bytes):
    """hello -> 90 00 <id 3>, start; between two actions hello again, answered `second`, then 12 00 00."""
    w = UsbmonWriter()
    w.control_in(T0, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    w.out(T0 + 0.1, 0x01, bytes([0x10, 0x01, 0x00, 0x00]))
    w.in_(T0 + 0.103, 0x81, bytes([0x90, 0x00, 0x00, 0x00]))
    w.out(T0 + 0.2, 0x01, bytes([0x11, 0x00, 0x00, 0x00]))
    w.in_(T0 + 0.203, 0x81, bytes([0x91, 0x00]))
    marks = []
    for i, v in enumerate((10, 20, 30, 40)):
        t = T0 + 1 + 1.5 * i
        if i == 2:
            w.out(t - 0.3, 0x01, bytes([0x10, 0x01, 0x00, 0x00]))
            w.in_(t - 0.297, 0x81, second)
            w.out(t - 0.2, 0x01, bytes([0x12, 0x00, 0x00, 0x00]))
            w.in_(t - 0.197, 0x81, bytes([0x92, 0x00]))
        w.out(t + 0.3, 0x01, bytes([0x30, v, 0x00, 0x00]))
        marks.append({"label": f"level {v}", "start": t, "end": t + 0.9})
    w.save(path)
    path.with_suffix(".pcap.actions.json").write_text(json.dumps(marks))
    return path


def test_other_messages_after_same_reply_are_not_a_branch(tmp_path):
    """The reply to hello did not change, so the different next message is not the device's doing."""
    p = analyze(_branch_capture(tmp_path / "same.pcap", bytes([0x90, 0x00, 0x00, 0x00])))
    assert [s["request"] for s in p.handshake] == ["11 00 00 00"]
    assert not any(s.get("branches") for s in p.handshake)


def test_branch_on_a_mode_byte(tmp_path):
    p = analyze(_branch_capture(tmp_path / "mode.pcap", bytes([0x90, 0x01, 0x00, 0x00])))
    hs = p.handshake
    assert [s["request"] for s in hs] == ["10 01 00 00", "11 00 00 00"] and hs[0]["expect"] == "90 ?? 00 00"
    cases = hs[0]["branches"]["cases"]
    assert hs[0]["branches"]["offset"] == 1 and list(cases) == ["00", "01"]
    assert [x["request"] for x in cases["01"]["steps"]] == ["12 00 00 00"]
    assert [c.name for c in p.commands] == ["level"] and len(p.commands[0].samples) == 4
    out = _driver(tmp_path, p, "drv_mode")
    fake, sent = _fake([bytes([0x90, 0x01, 0x00, 0x00]), bytes([0x92, 0x00])])
    assert out.Device(fake).branches == {1: 0x01}
    assert [s for _, s in sent] == [bytes([0x10, 1, 0, 0]), bytes([0x12, 0, 0, 0])]
