"""A real user capture: ASUS TUF Gaming LC III LCD AIO under the vendor app on Windows (USBPcap).

Shared by the owner in liquidctl#936 with permission to keep a trimmed copy as a test. Only this
device's traffic is kept (setup, the first frames and the frames around each brightness change),
and the JPEG image data is blanked; see tests/data/SOURCES.md.
"""
import gzip
from pathlib import Path

from usb_rea.pcap import find_ids, read_transfers
from usb_rea.pipeline import analyze

DATA = Path(__file__).parent / "data" / "asus-tuf-lc3-lcd.pcap.gz"


def capture(tmp_path):
    p = tmp_path / "lc3.pcap"
    p.write_bytes(gzip.decompress(DATA.read_bytes()))
    return p


def test_usbpcap_complete_stage_carries_descriptor(tmp_path):
    # USBPcap puts the GET_DESCRIPTOR reply in the "complete" record (stage 3)
    ts = read_transfers(capture(tmp_path))
    assert find_ids(ts)[2] == (0x0B05, 0x1C7B)


def test_brightness_command_and_jpeg_stream(tmp_path):
    proto = analyze(capture(tmp_path), labels=["brightness 0", "brightness 50", "brightness 100"])
    d = proto.to_dict()
    assert (d["vid"], d["pid"]) == (0x0B05, 0x1C7B)
    (s,) = d["streams"]
    assert s["endpoint"] == 3 and s["format"] == "jpeg" and s["size"] == [320, 320]
    assert s["first_header"] == "08 nn 00 80" and s["next_header"] == "08 ii 00 00"
    assert s["frames"] >= 20
    (c,) = d["commands"]
    assert c["endpoint"] == 1 and c["length"] == 440
    assert any(f["offset"] == 4 and f["kind"] == "value" for f in c["fields"])
