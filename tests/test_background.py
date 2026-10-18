"""Background traffic: status polls / keep-alives the vendor app sends regardless of clicks."""
import pytest

from usb_rea.actions import find_background, segment_by_gaps
from usb_rea.pcap import read_transfers
from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.synth import capture_from_messages, encode, make_capture

LAMP = ["brightness 0%", "brightness 25%", "brightness 50%", "brightness 75%", "brightness 100%",
        "power off", "power on", "hue 0", "hue 120", "hue 240"]


def _same(p, q):
    a = {c.name: [f.describe() for f in c.fields] for c in p.commands}
    b = {c.name: [f.describe() for f in c.fields] for c in q.commands}
    assert a == b


@pytest.mark.parametrize("period", [0.25, 0.7, 2.0])
def test_labels_ignore_status_polls(tmp_path, period):
    clean, m = make_capture(tmp_path / "clean.pcap")
    m.unlink()
    noisy, m = make_capture(tmp_path / "poll.pcap", poll=period)
    m.unlink()
    p = analyze(noisy, labels=LAMP)
    _same(p, analyze(clean, labels=LAMP))
    assert p.commands[0].encode(50) == encode("brightness", 50)
    assert len(p.background) == 1 and p.background[0]["payload"] == "aa 10 00 00 ba"


def test_polls_break_naive_segmentation(tmp_path):
    # without setting polls aside, the pauses between clicks are full of status requests
    cap, m = make_capture(tmp_path / "poll.pcap", poll=0.25)
    m.unlink()
    marks = segment_by_gaps(read_transfers(cap), LAMP)
    labels_with_cmd = [mk["end"] - mk["start"] for mk in marks]
    assert max(labels_with_cmd) > 1.0  # some "action" swallowed several clicks


def test_markers_with_polls_and_control_transport(tmp_path):
    cap, _ = make_capture(tmp_path / "poll.pcap", poll=0.33, transport="control")
    clean, _ = make_capture(tmp_path / "clean.pcap", transport="control")
    p = analyze(cap)
    _same(p, analyze(clean))
    assert p.background and p.background[0]["setup"]
    md = render(p)
    assert "Background traffic (ignored)" in md and "`aa 10 00 00 ba`" in md


def test_constant_apply_packet_is_not_background(tmp_path):
    # write + identical "apply" on every click, clicks at a perfectly steady pace
    msgs = [(f"level {v}", [bytes([0x12, 0x34, v, 0]), bytes([0x12, 0x99, 1, 0])], ("bulk", 2))
            for v in (0, 10, 20, 30, 40, 50)]
    msgs += [(f"mode {v}", bytes([0x30, v]), ("bulk", 2)) for v in (0, 1, 2)]
    cap, m = capture_from_messages(tmp_path / "apply.pcap", msgs, 0x1234, 0x5678)
    assert find_background(read_transfers(cap)) == []
    m.unlink()
    p = analyze(cap, labels=[x[0] for x in msgs])
    c = {c.name: c for c in p.commands}
    assert set(c) == {"level", "mode"} and len(c["level"].steps) == 1
    assert p.background == []


def test_no_polls_no_background(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan")
    assert analyze(cap).background == []


@pytest.mark.parametrize("period", [0.25, 0.7])
def test_polls_with_sequence_number(tmp_path, period):
    # status request carries a counter byte, so its checksum changes too: no two copies are equal
    clean, m = make_capture(tmp_path / "clean.pcap")
    m.unlink()
    noisy, m = make_capture(tmp_path / "seq.pcap", poll=period, poll_seq=True)
    m.unlink()
    p = analyze(noisy, labels=LAMP)
    _same(p, analyze(clean, labels=LAMP))
    assert len(p.background) == 1 and p.background[0]["payload"] == "aa 10 ?? 00 ??"
    assert "`aa 10 ?? 00 ??`" in render(p)


def test_value_stepped_by_one_is_not_background(tmp_path):
    # a user clicking "level +1" at a perfectly steady pace looks like a counter; too few to count
    msgs = [(f"level {v}", bytes([0x40, 0x01, v, (0x41 + v) & 0xFF]), ("bulk", 2)) for v in range(7)]
    cap, m = capture_from_messages(tmp_path / "step.pcap", msgs, 0x1234, 0x5678)
    assert find_background(read_transfers(cap)) == []
