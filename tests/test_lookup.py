"""VID:PID lookup before capturing. Never touches the network: OpenDeviceDB answers are faked."""
import asyncio
import json
import re

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
          "sources": ["openrgb"], "identifiers": {"usb": ["1e71:20aa"]}},
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
    assert lookup.parse_id("ID 1e71:170e") == (0x1E71, 0x170E)
    assert lookup.parse_id("id 1e71:170e") == (0x1E71, 0x170E)
    with pytest.raises(ValueError, match="capture"):
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
    assert set(u["same_vendor"]) >= {"liquidctl", "OpenRGB"}
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
    u = lookup.lookup(0x1E71, 0x20AA, online=True, fetch=fake_fetch)
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


def test_expanded_known_devices():
    """IDs added from public driver sources after the first lookup release."""
    assert len(lookup.KNOWN) >= 200
    a = lookup.lookup(0x1E71, 0x2001)  # NZXT HUE 2, liquidctl smart_device.py
    assert a["status"] == "documented" and any(p["project"] == "liquidctl" for p in a["projects"])
    assert any(p["project"] == "OpenRGB" for p in a["projects"])
    r = lookup.lookup(0x1038, 0x1836)  # Aerox 3, rivalcfg
    assert r["projects"][0]["project"] == "rivalcfg" and "Aerox 3" in r["product"]
    u = lookup.lookup(0x1CBE, 0x0046)  # Turing 4.6-inch USB
    assert "turing" in u["projects"][0]["project"]
    w = lookup.lookup(0x1A86, 0xFE0C)  # WeAct
    assert "serial number" in (w.get("limits") or "")
    tt = lookup.lookup(0x264A, 0x1FA5)  # Thermaltake Riing, OpenRGB
    assert tt["projects"][0]["project"] == "OpenRGB"
    xt = lookup.lookup(0x1B1C, 0x0C2D)  # H100i Pro XT V2, OpenRGB only
    assert xt["projects"][0]["project"] == "OpenRGB"


def test_docs_list_every_known_id():
    from pathlib import Path
    docs = Path(__file__).resolve().parents[1] / "docs" / "known-devices.md"
    text = docs.read_text()
    missing = [f"{vid:04x}:{pid:04x}" for vid, pid in lookup.KNOWN if f"{vid:04x}:{pid:04x}" not in text]
    assert missing == []


def test_cli_lookup_lsusb_and_bad_id(capsys):
    assert main(["lookup", "ID 1e71:170e"]) == 0
    assert "documented" in capsys.readouterr().out
    assert main(["lookup", "not-an-id"]) == 2
    err = capsys.readouterr().err
    assert "VID:PID" in err and "capture" in err


def test_more_known_devices_and_no_duplicate_ids():
    """Thermalright LCD/LED IDs and liquidctl's experimental MSI Coreliquid matches."""
    from pathlib import Path
    assert len(lookup.KNOWN) >= 267
    a = lookup.lookup(0x0402, 0x3922)  # Frozen Warframe, SCSI LCD
    assert a["status"] == "documented" and "Frozen Warframe" in a["product"]
    assert a["projects"][0]["project"] == "linux-thermalright-lcd-control"
    assert a["projects"][0]["url"].endswith("device_0402_3922.py")
    led = lookup.lookup(0x0416, 0x8001)
    assert "generic" in (led.get("limits") or "")
    msi = lookup.lookup(0x0DB0, 0xCA00)
    assert msi["projects"][0]["url"].endswith("msi.py") and "unsafe" in msi["limits"]
    # every _dev() call adds a new key; a repeated VID:PID would silently overwrite an entry
    src = (Path(__file__).resolve().parents[1] / "src" / "usb_rea" / "lookup.py").read_text()
    calls = re.findall(r"^_dev\((0x[0-9A-Fa-f]{4}), (0x[0-9A-Fa-f]{4}),", src, re.M)
    assert len(calls) == len(set(calls)) == len(lookup.KNOWN)
