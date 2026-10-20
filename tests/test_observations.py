"""'seen <name> <value>' markers: naming and scaling device readings from what the vendor app shows."""
import importlib.util
import json
from unittest import mock

from usb_rea.actions import append_marker, load_markers
from usb_rea.model import is_observation, split_observation
from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.scaffold import generate
from usb_rea.synth import FAN_ACTIONS, UsbmonWriter, device_descriptor, fan_status, make_capture

T0 = 1_760_000_000.0


def _poll(r):
    return next(x for x in r.responses if x.query.startswith(("poll", "GET_REPORT")))


def _named(r):
    return {f.name: f for f in r.fields if f.name}


def test_parse_observation_labels():
    assert split_observation("seen rpm 1180") == [("rpm", 1180.0)]
    assert split_observation("Seen RPM=1180, temp 34.5°C") == [("rpm", 1180.0), ("temp", 34.5)]
    assert split_observation("seen fan speed 1180rpm") == [("fan speed", 1180.0)]
    assert split_observation("seen pump on, alarm off") == [("pump", 1.0), ("alarm", 0.0)]
    assert split_observation("fan 1200") == [] and not is_observation("screen 3") and is_observation("seen")


def test_observation_markers_do_not_end_actions(tmp_path):
    m = tmp_path / "m.json"
    append_marker(m, "fan 1200", 10.0)
    append_marker(m, "seen rpm 1180", 10.5)
    append_marker(m, "fan 800", 12.0)
    marks = {x["label"]: x for x in load_markers(m)}
    assert marks["fan 1200"]["end"] == 12.0 and marks["seen rpm 1180"]["end"] == 10.5
    assert marks["fan 800"]["end"] == float("inf")


def test_fan_readings_named(tmp_path):
    plain = analyze(make_capture(tmp_path / "a.pcap", device="fan", poll=0.5)[0])
    seen = analyze(make_capture(tmp_path / "b.pcap", device="fan", poll=0.5, observe=True)[0])
    # observation markers are not actions: commands, background and segmentation are unchanged
    assert [(c.name, c.samples, [f.describe() for f in c.fields]) for c in seen.commands] == \
           [(c.name, c.samples, [f.describe() for f in c.fields]) for c in plain.commands]
    assert seen.unmatched == plain.unmatched == [] and seen.background == plain.background
    r = _poll(seen)
    n = _named(r)
    assert (n["rpm"].offset, n["rpm"].width, n["rpm"].endian, n["rpm"].scale, n["rpm"].bias) == (2, 2, "le", 1.0, 0.0)
    assert (n["temp"].offset, n["temp"].width) == (4, 1) and n["temp"].kind == "reading"
    assert all(raw == v for v, raw, _, _ in n["rpm"].observed) and r.explained == 7
    assert len(seen.observations) == 12 and all(o["matched"] for o in seen.observations)
    assert not any("no label to explain" in x for x in r.notes)
    md = render(seen)
    assert "`u16le rpm = raw, seen" in md and "## Observations (what the vendor app showed)" in md
    d = json.loads(json.dumps(seen.to_dict(), default=str))
    f = next(x for x in d["responses"] if x["query"] == "poll 1")["fields"][2]
    assert f["kind"] == "reading" and f["name"] == "rpm" and f["limits"]
    assert d["observations"][0]["matched"] == ["poll 1 bytes 2-3"]


def test_driver_returns_named_values(tmp_path):
    proto = analyze(make_capture(tmp_path / "fan.pcap", device="fan", poll=0.5, observe=True)[0])
    path = tmp_path / "drv.py"
    path.write_text(generate(proto))
    spec = importlib.util.spec_from_file_location("drv_obs", path)
    drv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drv)
    fake = mock.MagicMock()
    fake.__iter__.return_value = []
    fake.read.return_value = fan_status(1180, 34)
    out = drv.Device(fake).query_poll_1()
    assert out["rpm"] == 1180 and out["temp"] == 34 and out["ok"] and "reading_2" not in out


def _report_capture(path, raw_of, shown, n=20, marks=(), delay=0.05):
    """GET_REPORT(Input 3) every 0.4 s answering 03 <raw bytes> 00, plus 'seen' markers `delay` s after
    the replies listed in `shown` (reply index -> label)."""
    w = UsbmonWriter()
    w.control_in(T0, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    marks = list(marks)
    for i in range(n):
        tp = T0 + 0.5 + 0.4 * i
        data = bytes([0x03]) + raw_of(i) + b"\x00"
        w.control_in(tp, bytes([0xA1, 0x01, 0x03, 0x01, 0, 0, len(data), 0]), data)
        if i in shown:
            marks.append({"label": shown[i], "start": tp + delay})
    w.save(path)
    path.with_suffix(".pcap.actions.json").write_text(json.dumps(marks))
    return path


def test_linear_scale_needs_three_observations(tmp_path):
    temps = [20 + (i % 7) * 0.5 for i in range(20)]       # device sends half degrees + 40
    raw = lambda i: bytes([int(temps[i] * 2 + 40)])
    three = {i: f"seen temp {temps[i]:g}" for i in (1, 3, 5)}  # 20.5, 21.5, 22.5
    p = analyze(_report_capture(tmp_path / "t.pcap", raw, three))
    f = _named(_poll(p))["temp"]
    assert (f.scale, f.bias) == (2.0, 40.0) and "(raw - 40) / 2" in f.describe()
    two = {1: three[1], 5: three[5]}                         # two points always fit a line: not enough
    p = analyze(_report_capture(tmp_path / "t2.pcap", raw, two))
    assert not _named(_poll(p)) and not any(o["matched"] for o in p.observations)


def test_two_byte_readings_combined_as_u16(tmp_path):
    rpms = [800, 1210, 2650, 3990, 1500, 2200]               # < 8 replies: decode keeps two u8 readings
    for delay in (0.05, -0.05):                              # marker typed after the reply, or just before
        p = analyze(_report_capture(tmp_path / "u.pcap", lambda i: rpms[i].to_bytes(2, "big"),
                                    {0: "seen rpm 800", 2: "seen rpm 2650", 4: "seen rpm 1500"}, n=6, delay=delay))
        f = _named(_poll(p))["rpm"]
        assert (f.offset, f.width, f.endian) == (1, 2, "be") and f.limits == (800, 3990)
        assert [x.offset for x in _poll(p).fields] == [0, 1, 3] and [x[1] for x in f.observed] == [800, 2650, 1500]


def test_four_byte_readings_combined_as_u32(tmp_path):
    ups = [16_900_000 + 3_700_123 * i + (i * i * 977) for i in range(20)]   # uptime: all 4 bytes vary
    p = analyze(_report_capture(tmp_path / "up.pcap", lambda i: ups[i].to_bytes(4, "little"),
                                {i: f"seen uptime {ups[i]}" for i in (2, 9, 15)}))
    f = _named(_poll(p))["uptime"]
    assert (f.offset, f.width, f.endian, f.scale, f.bias) == (1, 4, "le", 1.0, 0.0)
    assert [x.offset for x in _poll(p).fields] == [0, 1, 5] and "(bytes 1-4, u32le)" in render(p)
    # energy in Wh below 2**24 (high byte stays 0x00), shown by the app in kWh: raw = value * 1000
    wh = [70_000 + 241_000 * i + 1000 * (i * i % 7) for i in range(20)]
    p = analyze(_report_capture(tmp_path / "e.pcap", lambda i: wh[i].to_bytes(4, "big"),
                                {i: f"seen energy {wh[i] / 1000:g}" for i in (1, 6, 12)}))
    f = _named(_poll(p))["energy"]
    assert (f.offset, f.width, f.endian, f.scale, f.bias) == (1, 4, "be", 1000.0, 0.0)
    assert f.limits == (70_000, wh[-1])
    src = generate(p)
    compile(src, "drv.py", "exec")
    assert "'name': 'energy', 'offset': 1, 'width': 4, 'endian': 'be'" in src


def test_wrong_observations_get_no_name(tmp_path):
    raw = lambda i: bytes([30 + i % 4])
    p = analyze(_report_capture(tmp_path / "w.pcap", raw, {1: "seen temp 70", 6: "seen temp 12", 11: "seen temp 99"}))
    r = _poll(p)
    assert not _named(r) and r.fields[1].kind == "reading" and r.explained == 2
    assert [o["matched"] for o in p.observations] == [[], [], []]
    assert "| seen temp 70 | " in render(p) and "0 of 3 matched" in render(p)
    # too far from any reply (> 1 s): not used at all
    p = analyze(_report_capture(tmp_path / "far.pcap", raw, {}, marks=[
        {"label": "seen temp 30", "start": T0 + 30}, {"label": "seen temp 31", "start": T0 + 40}]))
    assert not _named(_poll(p))


def test_ambiguous_name_left_out(tmp_path):
    raw = lambda i: bytes([30 + i % 5, 30 + i % 5 if i in (1, 3) else 60 + i % 3])  # equal when observed
    p = analyze(_report_capture(tmp_path / "a.pcap", raw, {1: "seen temp 31", 3: "seen temp 33"}))
    r = _poll(p)
    assert not _named(r) and any("fits several readings" in x for x in r.notes)


def test_observations_never_become_commands(tmp_path):
    cap, m = make_capture(tmp_path / "fan.pcap", device="fan", poll=0.5, observe=True)
    p = analyze(cap)
    assert [c.name for c in p.commands] == ["fan", "color", "mode"]
    assert not any("seen" in s[0] for c in p.commands for s in c.samples)
    m.unlink()   # --labels mode: a 'seen' label has no timestamp, so it is skipped
    p = analyze(cap, labels=FAN_ACTIONS[:4] + ["seen rpm 1200"] + FAN_ACTIONS[4:])
    assert [c.name for c in p.commands] == ["fan", "color", "mode"] and p.observations == []


def _flags(i):
    return bytes([0x40 | (i % 2) | (i % 3 == 2) << 3])   # bit 0 pump, bit 3 alarm, bit 6 always set


def test_on_off_flags_named_by_bit(tmp_path):
    shown = {1: "seen pump on alarm off", 2: "seen pump off alarm on", 4: "seen pump off, alarm off"}
    p = analyze(_report_capture(tmp_path / "f.pcap", _flags, shown))
    r = _poll(p)
    n = _named(r)
    assert (n["pump"].offset, n["pump"].bit_offset) == (1, 0) and (n["alarm"].offset, n["alarm"].bit_offset) == (1, 3)
    assert [x[1] for x in n["pump"].observed] == [1, 0, 0] and r.explained == 3
    assert "bit 3: alarm (1 = on)" in n["alarm"].describe()
    assert all(o["matched"] for o in p.observations) and p.observations[0]["matched"] == ["GET_REPORT Input 0x03 byte 1 bit 0"]
    assert not any("bits other than" in x for x in r.notes)
    md = render(p)
    assert "`alarm` (byte 1, bit 3) is on when the bit is 1" in md and "| pump on |" in md
    path = tmp_path / "drv.py"
    path.write_text(generate(p))
    spec = importlib.util.spec_from_file_location("drv_flags", path)
    drv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drv)
    fake = mock.MagicMock()
    fake.__iter__.return_value = []
    fake.ctrl_transfer.return_value = bytes([0x03, 0x49, 0x00])
    q = next(getattr(drv.Device(fake), m) for m in dir(drv.Device) if m.startswith("query_"))
    out = q()
    assert out["pump"] is True and out["alarm"] is True and out["ok"]


def test_flags_need_both_states_and_one_bit(tmp_path):
    only_on = {1: "seen pump on", 3: "seen pump on"}
    assert not _named(_poll(analyze(_report_capture(tmp_path / "o.pcap", _flags, only_on))))
    together = lambda i: bytes([0x03 * (i % 2)])           # bits 0 and 1 always flip together
    r = _poll(analyze(_report_capture(tmp_path / "t.pcap", together, {1: "seen pump on", 2: "seen pump off"})))
    assert not _named(r) and any("fits several bits" in x for x in r.notes)
    extra = lambda i: bytes([(i % 2) | (i % 4 == 3) << 5])  # bit 5 changes too but was never named
    r = _poll(analyze(_report_capture(tmp_path / "e.pcap", extra, {1: "seen pump on", 2: "seen pump off"})))
    assert _named(r)["pump"].bit_offset == 0 and any("mask 0x20" in x for x in r.notes)
