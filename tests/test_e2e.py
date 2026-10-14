import asyncio
import importlib.util
import sys
from unittest import mock

import pytest

from usb_rea.cli import main
from usb_rea.pipeline import analyze
from usb_rea.scaffold import generate
from usb_rea.synth import make_capture, encode


def test_generated_driver_sends_correct_bytes(tmp_path):
    cap, _ = make_capture(tmp_path / "lamp.pcap")
    src = generate(analyze(cap))
    path = tmp_path / "drv.py"
    path.write_text(src)
    compile(src, str(path), "exec")
    spec = importlib.util.spec_from_file_location("drv", path)
    drv = importlib.util.module_from_spec(spec)
    sent = []
    fake = mock.MagicMock()
    fake.__iter__.return_value = []
    fake.write.side_effect = lambda ep, data: sent.append((ep, bytes(data))) or len(data)
    spec.loader.exec_module(drv)
    d = drv.Device(fake)
    d.set_brightness(40)
    d.set_hue(200)
    d.set_power(0)
    assert sent == [(1, encode("brightness", 40)), (1, encode("hue", 200)), (1, encode("power", 0))]


def test_generated_driver_control(tmp_path):
    cap, _ = make_capture(tmp_path / "lamp.pcap", transport="control")
    src = generate(analyze(cap))
    assert "ctrl_transfer" in src and "(33, 9, 512, 0)" in src


def test_cli_demo(tmp_path, capsys):
    assert main(["demo", "-o", str(tmp_path / "d")]) == 0
    assert (tmp_path / "d" / "report.md").exists()
    assert "brightness" in capsys.readouterr().out


def test_cli_demo_dial(tmp_path, capsys):
    assert main(["demo", "--device", "dial", "-o", str(tmp_path / "d")]) == 0
    assert (tmp_path / "d" / "report.md").exists() and (tmp_path / "d" / "dial_driver.py").exists()
    out = capsys.readouterr().out
    assert "u32le" in out and "bits[0:4]" in out


def test_cli_report_and_transfers(tmp_path, capsys):
    cap, _ = make_capture(tmp_path / "lamp.pcap")
    assert main(["report", str(cap), "-o", str(tmp_path / "r.md")]) == 0
    assert "sum8" in (tmp_path / "r.md").read_text()
    assert main(["transfers", str(cap)]) == 0
    assert "aa 01" in capsys.readouterr().out


def test_replay_refuses_without_confirm():
    from usb_rea.replay import replay
    with pytest.raises(PermissionError):
        replay(0x1234, 0xABCD, 1, b"\x00")
    assert main(["replay", "0x1234", "0xabcd", "1", "00"]) == 2


def test_mcp_tools(tmp_path):
    pytest.importorskip("mcp")
    from usb_rea.mcp_server import build
    app = build()
    names = {t.name for t in asyncio.run(app.list_tools())}
    assert {"capture_start", "capture_stop", "mark_action", "diff_actions", "report",
            "scaffold_driver", "replay_packet", "hid_descriptor"} <= names
    cap, _ = make_capture(tmp_path / "lamp.pcap")
    res = asyncio.run(app.call_tool("report", {"capture": str(cap)}))
    assert "brightness" in str(res)
    res = asyncio.run(app.call_tool("replay_packet", {"vid": 1, "pid": 2, "endpoint": 1, "hex_data": "00"}))
    assert "refused" in str(res)


def test_mark(tmp_path):
    m = tmp_path / "m.json"
    assert main(["mark", "brightness 10%", "-m", str(m)]) == 0
    assert main(["mark", "brightness 20%", "-m", str(m)]) == 0
    import json
    d = json.loads(m.read_text())
    assert d[0]["end"] == d[1]["start"] and d[1]["end"] is None
