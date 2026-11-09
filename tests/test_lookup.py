"""VID:PID lookup before capturing. Never touches the network: OpenDeviceDB answers are faked."""
import asyncio
import json

import pytest

from usb_rea import lookup
from usb_rea.cli import main
from usb_rea.synth import capture_from_messages

USB_IDS = """# sample in the usb.ids format
1038  SteelSeries ApS
\t1702  Rival 100 Gaming Mouse
1e71  NZXT
\t170e  Kraken X
\t2007  Kraken X Series
1e72  Other Vendor
\t170e  Not this one
C 03  Human Interface Device
"""

INDEX = [{"id": "nzxt/hue-2", "vendor": "NZXT", "model": "Hue 2", "status": "controllable",
          "sources": ["openrgb"], "identifiers": {"usb": ["1e71:2001"]}},
         {"id": "acme/other", "vendor": "Acme", "model": "Other", "identifiers": {"chips": ["ESP32"]}}]
RECORD = {"id": "nzxt/hue-2", "projects": [{"name": "OpenRGB", "url": "https://gitlab.com/CalcProgrammer1/OpenRGB"}]}


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    def no_network(url, timeout=15.0):
        raise OSError("network disabled in tests")
    monkeypatch.setattr(lookup, "_fetch", no_network)
    monkeypatch.setattr(lookup, "USB_IDS_PATHS", ())
    monkeypatch.delenv("USB_IDS", raising=False)


def fake_fetch(url):
    if url.endswith("/index.json"):
        return json.dumps(INDEX).encode()
    if url.endswith("/devices/nzxt/hue-2.json"):
        return json.dumps(RECORD).encode()
    raise OSError(404)


def test_parse_id():
    assert lookup.parse_id("1e71:170e") == (0x1E71, 0x170E)
    assert lookup.parse_id("0x1E71:0x170E") == (0x1E71, 0x170E)
    assert lookup.parse_id(" 1038 1702 ") == (0x1038, 0x1702)
    with pytest.raises(ValueError):
        lookup.parse_id("kraken")


def test_known_devices_offline():
    k = lookup.lookup(0x1E71, 0x170E)
    assert k["status"] == "documented" and k["vendor"] == "NZXT" and "Kraken X" in k["product"]
    assert any(p["project"] == "liquidctl" and p["url"].endswith("kraken2.py") for p in k["projects"])
    assert "opendevicedb" not in k
    r = lookup.lookup(0x1038, 0x1702)
    assert r["projects"][0]["project"] == "rivalcfg"
    t = lookup.lookup(0x1A86, 0x5722)
    assert "turing" in t["projects"][0]["project"] and "serial number" in t["limits"]
    assert lookup.lookup(0x87AD, 0x70DB)["projects"][0]["project"] == "linux-thermalright-lcd-control"
    assert "case study" in lookup.lookup(0x0B05, 0x1C7B)["projects"][0]["project"]


def test_unknown_stays_unknown():
    u = lookup.lookup(0x1E71, 0x9999)
    assert u["status"] == "unknown" and u["projects"] == [] and u["product"] is None
    assert u["same_vendor"] == ["liquidctl"]
    text = lookup.render(u)
    assert "unknown" in text and "--online" in text
    nobody = lookup.lookup(0xFFFF, 0x0001)
    assert nobody["vendor"] is None and "unknown device" in lookup.render(nobody)


def test_usb_ids_names(tmp_path):
    assert lookup.usb_ids_names(USB_IDS, 0x1E71, 0x2007) == ("NZXT", "Kraken X Series")
    assert lookup.usb_ids_names(USB_IDS, 0x1E71, 0x1234) == ("NZXT", None)
    assert lookup.usb_ids_names(USB_IDS, 0x1E72, 0x170E) == ("Other Vendor", "Not this one")
    assert lookup.usb_ids_names(USB_IDS, 0x0003, 0x0000) == (None, None)
    f = tmp_path / "usb.ids"
    f.write_text(USB_IDS)
    u = lookup.lookup(0x1E71, 0x2007, usb_ids=f)
    assert u["names_from"] == "usb-rea" and u["usb_ids"]["product"] == "Kraken X Series"
    assert u["product"] == "NZXT Kraken X (X53, X63 or X73)"  # the curated name wins
    other = lookup.lookup(0x1E72, 0x170E, usb_ids=f)
    assert other["status"] == "unknown" and other["product"] == "Not this one" and other["names_from"] == "usb.ids"


def test_online_opendevicedb_faked():
    u = lookup.lookup(0x1E71, 0x2001, online=True, fetch=fake_fetch)
    assert u["status"] == "listed in OpenDeviceDB"
    rec = u["opendevicedb"]["records"][0]
    assert rec["id"] == "nzxt/hue-2" and rec["projects"][0]["project"] == "OpenRGB"
    assert "OpenRGB" in lookup.render(u)
    none = lookup.lookup(0x1E71, 0x9999, online=True, fetch=fake_fetch)
    assert none["status"] == "unknown" and "no record" in lookup.render(none)


def test_online_without_network_degrades():
    k = lookup.lookup(0x1E71, 0x170E, online=True)  # _fetch raises, as with no network
    assert k["status"] == "documented" and k["projects"]
    assert "network disabled" in k["opendevicedb"]["error"]
    assert "not reachable" in lookup.render(k)


def test_cli_lookup(capsys, tmp_path):
    assert main(["lookup", "1e71:170e"]) == 0
    out = capsys.readouterr().out
    assert "documented" in out and "liquidctl" in out
    assert main(["lookup", "1038:1702", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["projects"][0]["project"] == "rivalcfg"
    assert main(["lookup", "nonsense"]) == 2
    assert main(["lookup", "1e71:170e", "--online"]) == 0
    assert "not reachable" in capsys.readouterr().out


def test_cli_lookup_from_capture(capsys, tmp_path):
    cap, _ = capture_from_messages(tmp_path / "kraken.pcap", [("fan 50", bytes.fromhex("024d000032"), ("interrupt", 1))],
                                   0x1E71, 0x170E)
    assert main(["lookup", str(cap)]) == 0
    assert "1e71:170e" in capsys.readouterr().out
    empty = tmp_path / "empty.pcap"
    empty.write_bytes(bytes.fromhex("d4c3b2a1020004000000000000000000ffff0000dc000000"))
    assert main(["lookup", str(empty)]) == 1


def test_mcp_lookup_device():
    pytest.importorskip("mcp")
    from usb_rea.mcp_server import build
    app = build()
    tools = {t.name: t for t in asyncio.run(app.list_tools())}
    assert "lookup_device" in tools
    res = str(asyncio.run(app.call_tool("lookup_device", {"device": "1e71:170e"})))
    assert "liquidctl" in res and "documented" in res
    assert "error" in str(asyncio.run(app.call_tool("lookup_device", {"device": "nope"})))
