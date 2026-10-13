import pytest
from usb_rea.actions import load_markers, assign
from usb_rea.infer import infer
from usb_rea.pcap import read_transfers, find_ids
from usb_rea.report import render
from usb_rea.synth import make_capture, encode, VID, PID


def run(tmp_path, **kw):
    cap, marks = make_capture(tmp_path / "lamp.pcap", **kw)
    ts = read_transfers(cap)
    vid, pid = find_ids(ts).get(5, (None, None))
    return infer(assign(ts, load_markers(marks)), vid, pid)


@pytest.mark.parametrize("transport", ["bulk", "control"])
def test_lamp_protocol_recovered(tmp_path, transport):
    p = run(tmp_path, transport=transport)
    assert (p.vid, p.pid) == (VID, PID)
    cmds = {c.name: c for c in p.commands}
    assert set(cmds) == {"brightness", "power", "hue"}
    b = cmds["brightness"]
    kinds = [f.kind for f in b.fields]
    assert kinds == ["const", "command", "value", "const", "checksum"]
    assert b.fields[4].algo == "sum8"
    assert b.confidence == 1.0
    # the inferred encoder reproduces the real device protocol for unseen values
    for v in (10, 33, 90):
        assert b.encode(v) == encode("brightness", v)
    for v in (2, 100, 358):
        assert cmds["hue"].encode(v) == encode("hue", v)
    assert cmds["power"].encode(1) == encode("power", 1)


def test_report_has_evidence(tmp_path):
    md = render(run(tmp_path), "lamp.pcap")
    assert "1234:abcd" in md and "| brightness 50% |" in md and "sum8" in md


def test_xor_checksum_detected():
    from usb_rea.infer import infer
    from usb_rea.model import Action, Transfer
    acts = []
    for i, v in enumerate([0, 10, 20, 30]):
        body = bytes([0x5A, 0x07, v, 0x01])
        x = 0
        for c in body:
            x ^= c
        t = Transfer(i + 1, float(i), 1, 3, 0x02, 3, None, body + bytes([x]))
        acts.append(Action(f"speed {v}", i - 0.1, i + 0.1, [t]))
    c = infer(acts).commands[0]
    assert c.fields[4].kind == "checksum" and c.fields[4].algo == "xor8"
    assert c.fields[2].kind == "value" and c.fields[2].scale == 1


def test_background_chatter_ignored(tmp_path):
    from usb_rea.model import Action, Transfer
    acts = []
    for i, v in enumerate([1, 2, 3, 4]):
        ka = Transfer(10 * i + 1, i, 1, 3, 0x01, 3, None, b"\xff\xee")   # keepalive
        cmd = Transfer(10 * i + 2, i + 0.01, 1, 3, 0x01, 3, None, bytes([0x10, v]))
        acts.append(Action(f"mode {v}", i - 0.1, i + 0.5, [ka, cmd]))
    c = infer(acts).commands[0]
    assert c.length == 2 and c.fields[1].kind == "value"
