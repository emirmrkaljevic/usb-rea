"""Device replies: pairing queries with the IN data that answers them, and decoding it."""
import importlib.util
import json
import random
from unittest import mock

import pytest

from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.scaffold import generate
from usb_rea.synth import (FAN_ACTIONS, UsbmonWriter, capture_from_messages, device_descriptor, encode_fan,
                           fan_reply, fan_status, make_capture)


def _by(p):
    return {r.query: r for r in p.responses}


def _roles(r):
    return {f.offset: f for f in r.fields}


@pytest.mark.parametrize("period,transport", [(0.25, "bulk"), (0.7, "bulk"), (0.5, "control")])
def test_fan_status_poll_reply(tmp_path, period, transport):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", poll=period, transport=transport)
    p = analyze(cap)
    r = _by(p)["poll 1"]
    assert r.source == "background" and r.answered == r.queries == p.background[0]["count"]
    f = _roles(r)
    assert f[0].kind == "const" and f[0].const == 0xA5
    assert f[1].kind == "echo" and f[1].echo == 2 and f[1].const == 0x40        # echoed command id
    assert f[2].kind == "reading" and (f[2].width, f[2].endian) == (2, "le")    # current RPM
    assert 988 - 200 <= f[2].limits[0] and f[2].limits[1] <= 4012
    assert f[4].kind == "reading" and f[4].width == 1 and 35 <= f[4].limits[0] <= f[4].limits[1] <= 45
    assert f[6].kind == "checksum" and f[6].algo == "sum8" and f[6].covers == (0, 6)
    assert r.explained == 4 and any("no label to explain" in n for n in r.notes)


def test_poll_replies_also_with_labels(tmp_path):
    cap, m = make_capture(tmp_path / "fan.pcap", device="fan", poll=0.25)
    m.unlink()
    p = analyze(cap, labels=FAN_ACTIONS)
    assert [c.name for c in p.commands] == ["fan", "color", "mode"]
    assert _roles(_by(p)["poll 1"])[2].kind == "reading"


def test_command_reply_fitted_to_label(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan")
    r = _by(analyze(cap))
    f = _roles(r["fan"])
    assert f[1].kind == "echo" and f[1].const == 0x10 and f[1].echo == 2
    assert f[2].kind == "echo" and f[2].echo == 1 and f[2].const is None    # sequence number echoed
    assert f[3].kind == "value" and (f[3].width, f[3].endian, f[3].scale, f[3].bias) == (2, "le", 1.0, 0.0)
    assert f[5].kind == "checksum" and f[5].covers == (0, 5)
    assert _roles(r["mode"])[3].kind == "echo" and _roles(r["mode"])[3].echo == 3
    assert [s[0] for s in r["fan"].samples] == ["fan 800", "fan 1200", "fan 2650", "fan 4000"]


def test_poll_between_command_and_its_reply(tmp_path):
    # at 0.25 s the synthetic polls land a few ms before or after every click: replies must not swap
    cap, _ = make_capture(tmp_path / "lamp.pcap", poll=0.25)
    r = _by(analyze(cap))
    for name, cmd in (("brightness", 1), ("power", 2), ("hue", 3)):
        f = _roles(r[name])[1]
        assert (f.kind, f.const, f.echo) == ("echo", cmd, 1)
    assert _roles(r["poll 1"])[1].const == 0x10


def test_sequence_poll_reply_echoes_counter(tmp_path):
    cap, _ = make_capture(tmp_path / "seq.pcap", poll=0.7, poll_seq=True)
    p = analyze(cap)
    r = _by(p)["poll 1"]
    f = _roles(r)
    assert f[2].kind == "echo" and f[2].echo == 2
    assert r.query_payload == "aa 10 ?? 00 ??"
    kinds = {x.offset: x.kind for x in r.request.fields}
    assert kinds[2] == "counter" and kinds[4] == "checksum"


def _getreport_capture(path, labelled_noise=True):
    """Commands 'level N' (bulk OUT) answered with an ACK whose last byte is random, plus a
    GET_REPORT(Input, id 3) every 0.4 s answered with 03 <temp> 00."""
    rnd = random.Random(3)
    w = UsbmonWriter()
    t = 1_760_000_000.0
    w.control_in(t, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    t += 0.5
    marks, temp = [], 30
    for v in (0, 10, 20, 30, 40, 50):
        w.out(t + 0.3, 0x02, bytes([0x40, v, 0x00]))
        w.in_(t + 0.305, 0x82, bytes([0x41, rnd.randrange(256)]))
        marks.append({"label": f"level {v}", "start": t, "end": t + 1.0})
        t += 1.5
    tp = 1_760_000_000.2
    while tp < t:
        temp = min(40, max(25, temp + rnd.choice((-1, 0, 1))))
        w.control_in(tp, bytes([0xA1, 0x01, 0x03, 0x01, 0, 0, 3, 0]), bytes([0x03, temp, 0x00]))
        tp += 0.4
    w.save(path)
    path.with_suffix(".pcap.actions.json").write_text(json.dumps(marks))
    return path


def test_get_report_and_unexplained_reply_bytes(tmp_path):
    p = analyze(_getreport_capture(tmp_path / "gr.pcap"))
    r = _by(p)
    g = r["GET_REPORT Input 0x03"]
    assert g.source == "control read" and g.answered == g.queries > 10
    f = _roles(g)
    assert f[0].const == 3 and f[1].kind == "reading" and 25 <= f[1].limits[0] and f[2].const == 0
    lv = _roles(r["level"])
    assert lv[0].const == 0x41 and lv[1].kind == "reading"
    assert any("do not follow the action values" in n for n in r["level"].notes)
    md = render(p)
    assert "## Device responses" in md and "Reply to `GET_REPORT Input 0x03` (control read)" in md
    assert f"| level 10 | {r['level'].samples[1][1]} |" in md


def test_no_replies_no_section(tmp_path):
    msgs = [(f"level {v}", bytes([0x12, v]), ("bulk", 2)) for v in (0, 10, 20, 30)]
    cap, _ = capture_from_messages(tmp_path / "quiet.pcap", msgs, 0x1234, 0x5678)
    p = analyze(cap)
    assert p.responses == [] and "Device responses" not in render(p)


def test_json_output(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", poll=0.5)
    d = json.loads(json.dumps(analyze(cap).to_dict(), default=str))
    poll = next(r for r in d["responses"] if r["query"] == "poll 1")
    assert poll["request"]["setup"] is None and poll["fields"][2]["kind"] == "reading"


def _driver(tmp_path, proto):
    path = tmp_path / "drv.py"
    path.write_text(generate(proto))
    spec = importlib.util.spec_from_file_location("drv_resp", path)
    drv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drv)
    return drv


def test_driver_query_methods(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", poll=0.5)
    drv = _driver(tmp_path, analyze(cap))
    sent, replies = [], []
    fake = mock.MagicMock()
    fake.__iter__.return_value = []
    fake.write.side_effect = lambda ep, data: sent.append(bytes(data)) or len(data)
    fake.read.side_effect = lambda ep, n, timeout: replies.pop(0)
    d = drv.Device(fake)

    replies.append(fan_status(1834, 41))
    out = d.query_poll_1()
    assert out["ok"] and out["checksum_ok"] and out["reading_2"] == 1834 and out["reading_4"] == 41
    assert sent[-1] == bytes.fromhex("5a00400000001921")

    replies.append(fan_reply(encode_fan("fan", [1500], d.seq + 1), [1500]))
    out = d.query_fan(1500)
    assert out["ok"] and out["fan"] == 1500.0
    assert sent[-1] == encode_fan("fan", [1500], d.seq)

    bad = bytearray(fan_status(900, 39))
    bad[-1] ^= 0xFF
    replies.append(bytes(bad))
    assert d.query_poll_1()["checksum_ok"] is False


def test_driver_control_read(tmp_path):
    drv = _driver(tmp_path, analyze(_getreport_capture(tmp_path / "gr.pcap")))
    fake = mock.MagicMock()
    fake.__iter__.return_value = []
    fake.ctrl_transfer.return_value = bytes([3, 33, 0])
    out = drv.Device(fake).query_get_report_input_0x03()
    fake.ctrl_transfer.assert_called_with(0xA1, 1, 0x0103, 0, 3, 1000)
    assert out == {"raw": "03 21 00", "ok": True, "reading_1": 33}
