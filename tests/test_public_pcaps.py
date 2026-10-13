"""Parse real public captures (Wireshark SampleCaptures). Downloaded on demand; skipped offline."""
import hashlib
import urllib.request
from pathlib import Path

import pytest

from usb_rea.pcap import find_ids, read_transfers

BASE = "https://wiki.wireshark.org/uploads/__moin_import__/attachments/SampleCaptures/"
FILES = {
    "usb_memory_stick.pcap": "f1534b209593c7a82bbe95d0add0356b23a0abfba0f34ef550c96c3b00f2a17f",
    "usb_u3v_sample.pcapng": "f278c4178696d4a744e6e2894d08d1211e2f4aa058d0f23c1f9267d7813c2937",
}


def fetch(name):
    cache = Path.home() / ".cache" / "usb-rea" / "pcaps"
    cache.mkdir(parents=True, exist_ok=True)
    p = cache / name
    if not p.exists():
        try:
            with urllib.request.urlopen(BASE + name, timeout=20) as r:
                p.write_bytes(r.read())
        except Exception as e:  # offline / blocked
            pytest.skip(f"cannot download {name}: {e}")
    if hashlib.sha256(p.read_bytes()).hexdigest() != FILES[name]:
        p.unlink()
        pytest.skip(f"{name} changed upstream (sha256 mismatch)")
    return p


def test_usbmon_mass_storage():
    ts = read_transfers(fetch("usb_memory_stick.pcap"))
    assert find_ids(ts)[8] == (0x0D7D, 0x0150)
    outs = [t for t in ts if t.kind == "bulk" and t.is_out]
    assert len(outs) > 100 and all(t.data[:4] == b"USBC" for t in outs)
    assert any(t.data[:4] == b"USBS" for t in ts if t.kind == "bulk" and t.is_in)


def test_usbpcap_usb3_vision():
    ts = read_transfers(fetch("usb_u3v_sample.pcapng"))
    vid, pid = find_ids(ts)[19]
    assert vid == 0x2676
    outs = [t for t in ts if t.kind == "bulk" and t.is_out]
    assert len(outs) > 10 and all(t.data[:4] == b"U3VC" for t in outs)
