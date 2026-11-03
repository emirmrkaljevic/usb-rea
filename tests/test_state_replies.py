"""States the device reports in its status replies, and mode switches the app makes inside an action."""
import importlib.util
import json
from unittest import mock

import pytest

from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.scaffold import generate
from usb_rea.synth import (FAN_MODES, UsbmonWriter, device_descriptor, encode_fan, fan_reply, fan_status,
                           make_capture)


def _cmds(proto):
    return {c.name: c for c in proto.commands}


def _driver(tmp_path, proto, name):
    path = tmp_path / f"{name}.py"
    path.write_text(generate(proto))
    spec = importlib.util.spec_from_file_location(name, path)
    drv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drv)
    return drv


class FakeFan:
    """Answers status polls with the mode it is in; a mode command written to it changes that mode
    (unless `stuck`, a fan that ignores the command)."""

    def __init__(self, mode=0x00, stuck=False):
        self.mode, self.stuck, self.sent = mode, stuck, []
        self.dev = mock.MagicMock()
        self.dev.__iter__.return_value = []
        self.dev.write.side_effect = self.write
        self.dev.read.side_effect = lambda ep, n, timeout=1000: fan_status(1000, 38, self.mode)

    def write(self, ep, data):
        data = bytes(data)
        self.sent.append(data)
        if data[2] == 0x30 and not self.stuck:
            self.mode = data[3]
        return len(data)

    def cmds(self):
        return [m[2] for m in self.sent]


def test_color_only_sent_while_the_fan_reports_turbo(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", reported=True)
    proto = analyze(cap)
    c = _cmds(proto)
    assert [r["command"] for r in proto.states] == ["color"]
    req = c["color"].requires[0]
    assert (req["source"], req["state"], req["value"], req["reply"], req["where"]) == \
        ("reply", "mode", "turbo", "poll 1", "byte 5")
    assert req["count"] == 3 and req["other_values"] == ["auto", "balanced", "silent"]
    assert req["frames"] == c["color"].frames and len(req["reply_frames"]) == 3
    assert all(r < f for r, f in zip(req["reply_frames"], req["frames"]))   # the reply came before each color
    assert req["setter"]["command"] == "mode" and req["setter"]["value"] == 3.0 and req["setter"]["count"] == 3
    assert c["fan"].requires is None and c["mode"].requires is None   # mode is how the state is set
    assert any("only sent while the device reported mode turbo" in n for n in c["color"].notes)
    json.dumps(proto.to_dict())


def test_report_and_demo_text(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", reported=True)
    text = render(analyze(cap))
    assert "Only sent while the device reported `mode turbo` (poll 1 byte 5): 3x" in text
    assert "switches it with `mode 3`" in text


def test_no_reported_precondition_on_weak_evidence(tmp_path):
    # color seen while the fan reported turbo and while it reported silent: not tied to one mode
    acts = ["fan 800", "press mode 3", "color 255 0 0", "press mode 1", "color 0 128 255", "fan 1200",
            "mode 2", "fan 2650", "mode 3", "color 10 20 30", "mode 1", "fan 4000"]
    cap, _ = make_capture(tmp_path / "mixed.pcap", device="fan", reported=True, actions=acts)
    assert analyze(cap).states == []
    # without 'seen mode ...' markers the mode byte is an unnamed reading: no state to talk about
    cap, m = make_capture(tmp_path / "unnamed.pcap", device="fan", reported=True)
    m.write_text(json.dumps([x for x in json.loads(m.read_text()) if not x["label"].startswith("seen")]))
    proto = analyze(cap)
    assert proto.states == [] and _cmds(proto)["color"].requires is None


def test_driver_reads_the_mode_and_switches_it(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", reported=True)
    drv = _driver(tmp_path, analyze(cap), "fan_reported_driver")
    fan = FakeFan(mode=FAN_MODES[1])
    d = drv.Device(fan.dev)
    d.set_color(255, 0, 0)
    # poll (silent), mode 3, poll again (turbo), then the color
    assert fan.cmds() == [0x40, 0x30, 0x40, 0x20] and fan.sent[1][3] == 0x47
    d.set_color(0, 128, 255)
    assert fan.cmds()[4:] == [0x40, 0x20]   # already turbo: only checked
    fan.mode = FAN_MODES[2]                 # the user pressed the button on the fan
    d.set_fan(1200)
    d.set_color(1, 2, 3)
    assert fan.cmds()[6:] == [0x10, 0x40, 0x30, 0x40, 0x20]


def test_driver_strict_and_stuck(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", reported=True)
    drv = _driver(tmp_path, analyze(cap), "fan_reported_strict")
    fan = FakeFan(mode=FAN_MODES[1])
    with pytest.raises(drv.StateError, match=r"reports mode 'silent'.*set_mode\(3\)"):
        drv.Device(fan.dev, auto_state=False).set_color(255, 0, 0)
    assert fan.cmds() == [0x40]   # only asked
    stuck = FakeFan(mode=FAN_MODES[1], stuck=True)
    with pytest.raises(drv.StateError, match="still reports mode 'silent'"):
        drv.Device(stuck.dev).set_color(255, 0, 0)
    assert 0x20 not in stuck.cmds()


def test_driver_without_a_command_that_switches(tmp_path):
    # the mode is only ever changed with the fan's own button: the driver can check it, not set it
    acts = ["fan 800", "press mode 3", "color 255 0 0", "color 0 128 255", "press mode 1", "fan 1200",
            "fan 2650", "press mode 3", "color 10 20 30", "press mode 2", "fan 4000"]
    cap, _ = make_capture(tmp_path / "button.pcap", device="fan", reported=True, actions=acts)
    proto = analyze(cap)
    assert proto.states[0]["value"] == "turbo" and proto.states[0]["setter"] is None
    drv = _driver(tmp_path, proto, "fan_button_driver")
    fan = FakeFan(mode=FAN_MODES[2])
    with pytest.raises(drv.StateError, match="switch it on the device"):
        drv.Device(fan.dev).set_color(255, 0, 0)
    fan.mode = FAN_MODES[3]
    drv.Device(fan.dev).set_color(255, 0, 0)
    assert fan.cmds() == [0x40, 0x40, 0x20]


def test_mode_switch_inside_the_color_action(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", switch=True)
    proto = analyze(cap)
    c = _cmds(proto)
    assert list(c) == ["mode", "fan", "color"]
    color = c["color"]
    assert color.steps == [] and [f.const for f in color.fields if f.kind == "command"] == [0x20]
    assert [s[0] for s in color.samples][:2] == ["color 255 0 0", "color 0 128 255"]
    sw = color.switch
    assert (sw["state"], sw["enter"], sw["restore"], sw["count"], sw["packets"]) == ("mode", 3.0, "previous", 4, 3)
    assert sw["restore_values"] == [1.0, 2.0, 2.0, 1.0]
    assert all(a < f < b for a, f, b in zip(sw["enter_frames"], color.frames, sw["restore_frames"]))
    assert proto.switches[0]["command"] == "color" and proto.states == []
    assert color.confidence == 1.0 and not any("multi-packet" in n for n in color.notes)
    assert "Switches `mode` inside the action: 4x" in render(proto)


def test_driver_replays_the_switch(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", switch=True)
    drv = _driver(tmp_path, analyze(cap), "fan_switch_driver")
    fan = FakeFan()
    d = drv.Device(fan.dev)
    d.set_mode(2)
    d.set_color(255, 0, 0)
    assert fan.cmds() == [0x30, 0x30, 0x20, 0x30] and [m[3] for m in fan.sent if m[2] == 0x30] == [0x22, 0x47, 0x22]
    assert d.state["mode"] == 2.0
    seqs = [m[1] for m in fan.sent]
    assert seqs == sorted(seqs) and len(set(seqs)) == 4   # one counter across the switch
    fresh = FakeFan()
    drv.Device(fresh.dev).set_color(1, 2, 3)   # mode never set: nothing to put back
    assert fresh.cmds() == [0x30, 0x20]


def _wrapped(path, enters, backs):
    """Fan capture: 'mode 1', then colors each sent as mode <enter>, color, mode <back> (None: no last packet)."""
    w = UsbmonWriter()
    t = 1_760_000_000.0
    w.control_in(t, bytes([0x80, 6, 0, 1, 0, 0, 18, 0]), device_descriptor())
    t += 0.5
    marks, seq = [], 0x40
    plan = [("mode 1", [("mode", [1])]), ("mode 2", [("mode", [2])]), ("mode 3", [("mode", [3])])]
    for k, (e, b) in enumerate(zip(enters, backs)):
        rgb = [10 * k, 20 + k, 200 - k]
        pk = [("mode", [e]), ("color", rgb)] + ([("mode", [b])] if b else [])
        plan += [(f"color {rgb[0]} {rgb[1]} {rgb[2]}", pk), (f"fan {800 + 400 * k}", [("fan", [800 + 400 * k])])]
    for label, pkts in plan:
        for j, (name, vals) in enumerate(pkts):
            seq += 1
            msg = encode_fan(name, vals, seq)
            w.out(t + 0.3 + 0.03 * j, 0x01, msg)
            w.in_(t + 0.31 + 0.03 * j, 0x81, fan_reply(msg, vals if name == "fan" else [0]))
        marks.append({"label": label, "start": t, "end": t + 1.0})
        t += 1.5
    w.save(path)
    path.with_suffix(".pcap.actions.json").write_text(json.dumps(marks))
    return path


def test_switch_only_when_the_packets_agree(tmp_path):
    # back to a fixed mode 1 (the mode before was 3): a fixed restore value
    color = _cmds(analyze(_wrapped(tmp_path / "fixed.pcap", [2, 2, 2], [1, 1, 1])))["color"]
    assert (color.switch["enter"], color.switch["restore"]) == (2.0, 1.0)
    # no last packet: the app switched and left it there
    color = _cmds(analyze(_wrapped(tmp_path / "enter.pcap", [3, 3, 3], [None] * 3)))["color"]
    assert color.switch["restore"] is None and color.switch["packets"] == 2
    # the first packet picks different modes: kept as a 3-packet transaction, with a note
    proto = analyze(_wrapped(tmp_path / "mixed.pcap", [1, 2, 3], [1, 1, 1]))
    color = _cmds(proto)["color"]
    assert color.switch is None and len(color.steps) == 2 and proto.switches == []
    assert any("with different values" in n for n in color.notes)
    # the last packet is neither the mode from before nor one fixed value
    color = _cmds(analyze(_wrapped(tmp_path / "odd.pcap", [3, 3, 3], [1, 2, 1])))["color"]
    assert color.switch is None and any("neither the value from before" in n for n in color.notes)
