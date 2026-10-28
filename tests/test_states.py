"""Commands the vendor app only sent in one state of a mode command, and the driver's _require()."""
import importlib.util
from unittest import mock

import pytest

from usb_rea.pipeline import analyze
from usb_rea.report import render
from usb_rea.scaffold import generate
from usb_rea.synth import make_capture


def _cmds(proto):
    return {c.name: c for c in proto.commands}


def test_color_only_sent_in_mode_3(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", states=True)
    proto = analyze(cap)
    c = _cmds(proto)
    assert [r["command"] for r in proto.states] == ["color"]
    req = c["color"].requires[0]
    assert (req["state"], req["value"], req["count"], req["other_values"]) == ("mode", 3.0, 3, [1.0, 2.0])
    assert len(req["setter_frames"]) == 2 and req["frames"] == c["color"].frames
    assert c["fan"].requires is None and c["mode"].requires is None
    assert any("only sent while mode was 3" in n for n in c["color"].notes)
    assert "Only sent while `mode 3`: 3x" in render(proto)
    assert proto.to_dict()["commands"][2]["requires"][0]["value"] == 3.0


def test_no_precondition_without_a_known_or_changing_state(tmp_path):
    # default fan capture: fan and color come before any mode command, so their state is unknown
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan")
    assert analyze(cap).states == []
    # color in mode 3 and in mode 1: not tied to one state
    acts = ["mode 1", "fan 800", "color 1 2 3", "mode 3", "color 255 0 0", "color 0 128 255", "mode 2", "fan 1200"]
    cap, _ = make_capture(tmp_path / "mixed.pcap", device="fan", actions=acts)
    assert analyze(cap).states == []
    # the mode never changes while other commands run: nothing to compare against
    acts = ["mode 1", "mode 2", "mode 3", "color 255 0 0", "color 0 128 255", "color 10 20 30"]
    cap, _ = make_capture(tmp_path / "flat.pcap", device="fan", actions=acts)
    assert analyze(cap).states == []


def test_states_only_for_the_fan(tmp_path):
    with pytest.raises(ValueError):
        make_capture(tmp_path / "lamp.pcap", states=True)


def _driver(tmp_path, proto):
    path = tmp_path / "fan_states_driver.py"
    path.write_text(generate(proto))
    spec = importlib.util.spec_from_file_location("fan_states_driver", path)
    drv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drv)
    return drv


def _fake():
    sent = []
    fake = mock.MagicMock()
    fake.__iter__.return_value = []
    fake.write.side_effect = lambda ep, data: sent.append(bytes(data)) or len(data)
    return fake, sent


def test_driver_sets_the_mode_before_color(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", states=True)
    drv = _driver(tmp_path, analyze(cap))
    fake, sent = _fake()
    d = drv.Device(fake)
    d.set_color(255, 0, 0)
    assert [m[2] for m in sent] == [0x30, 0x20] and sent[0][3] == 0x47   # mode 3, then color
    d.set_color(0, 128, 255)
    d.set_fan(1200)
    assert [m[2] for m in sent] == [0x30, 0x20, 0x20, 0x10]   # already in mode 3; fan needs no mode
    d.set_mode(1)
    d.set_color(1, 2, 3)
    assert [m[2] for m in sent][-3:] == [0x30, 0x30, 0x20] and sent[-2][3] == 0x47


def test_driver_strict_mode_raises(tmp_path):
    cap, _ = make_capture(tmp_path / "fan.pcap", device="fan", states=True)
    drv = _driver(tmp_path, analyze(cap))
    fake, sent = _fake()
    d = drv.Device(fake, auto_state=False)
    with pytest.raises(drv.StateError, match=r"set_mode\(3\)"):
        d.set_color(255, 0, 0)
    assert sent == []
    d.set_mode(3)
    d.set_color(255, 0, 0)
    assert [m[2] for m in sent] == [0x30, 0x20]


def test_cli_demo_fan_shows_state(tmp_path, capsys):
    from usb_rea.cli import main
    assert main(["demo", "--device", "fan", "-o", str(tmp_path / "d")]) == 0
    out = capsys.readouterr().out
    assert "color only sent while mode 3 (3x; other commands ran in mode 1, 2)" in out
    assert "self._require('mode', 3.0, self.set_mode)" in (tmp_path / "d" / "fan_driver.py").read_text()
