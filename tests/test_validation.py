"""Validation against protocols documented by established open-source drivers.

The packets below are produced exactly the way the upstream driver builds them (see links);
usb-rea must recover the same structure without being told.

* liquidctl, NZXT Kraken X42/X52/X62/X72 (1e71:170e), set_instantaneous_speed():
  https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/kraken2.py
  _write([0x2, 0x4d, cbase & 0x70, 0, duty]) padded to 65 bytes; cbase fan=0x80, pump=0xc0
* rivalcfg, SteelSeries Rival 100 (1038:1702), HID output reports:
  https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival100.py
  sensitivity1 [0x03, 0x01, choice], polling_rate [0x04, 0x00, choice], color [0x05, 0x00, r, g, b]
"""
from usb_rea.pipeline import analyze
from usb_rea.synth import capture_from_messages


def kraken2(duty_by_channel):
    out = []
    for ch, duty in duty_by_channel:
        cbase = {"fan": 0x80, "pump": 0xC0}[ch]
        data = [0x2, 0x4D, cbase & 0x70, 0, duty]
        out.append((f"{ch} {duty}%", bytes(data + [0] * (65 - len(data))), ("interrupt", 0x01)))
    return out


def test_liquidctl_kraken2(tmp_path):
    msgs = kraken2([("fan", 25), ("fan", 50), ("fan", 75), ("fan", 100),
                    ("pump", 60), ("pump", 80), ("pump", 100)])
    cap, _ = capture_from_messages(tmp_path / "kraken.pcap", msgs, 0x1E71, 0x170E)
    p = analyze(cap)
    assert (p.vid, p.pid) == (0x1E71, 0x170E)
    c = {c.name: c for c in p.commands}
    for name, cid in (("fan", 0x00), ("pump", 0x40)):
        f = {x.offset: x for x in c[name].fields}
        assert (f[0].const, f[1].const) == (0x02, 0x4D)
        assert f[2].kind == "command" and f[2].const == cid
        assert f[4].kind == "value" and (f[4].scale, f[4].bias) == (1, 0)
        assert c[name].length == 65
    assert c["fan"].encode(42) == kraken2([("fan", 42)])[0][1]


RIVAL_SETUP = bytes([0x21, 0x09, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00])  # SET_REPORT, Output, id 0
SENS = {250: 0x08, 500: 0x07, 1000: 0x06, 1250: 0x05, 1500: 0x04, 1750: 0x03, 2000: 0x02, 4000: 0x01}
POLL = {125: 0x04, 250: 0x03, 500: 0x02, 1000: 0x01}


def test_rivalcfg_rival100(tmp_path):
    msgs = [(f"sensitivity1 {d}", bytes([0x03, 0x01, SENS[d]]), ("control", RIVAL_SETUP)) for d in SENS]
    msgs += [(f"polling rate {r}", bytes([0x04, 0x00, POLL[r]]), ("control", RIVAL_SETUP)) for r in POLL]
    msgs += [(f"color {r} {g} {b}", bytes([0x05, 0x00, r, g, b]), ("control", RIVAL_SETUP))
             for r, g, b in ((255, 24, 0), (0, 0, 255), (10, 200, 30))]
    cap, _ = capture_from_messages(tmp_path / "rival.pcap", msgs, 0x1038, 0x1702)
    p = analyze(cap)
    c = {c.name: c for c in p.commands}
    s = {x.offset: x for x in c["sensitivity1"].fields}
    assert s[0].kind == "command" and s[0].const == 0x03
    assert s[2].kind == "lookup" and s[2].table == {float(k): v for k, v in SENS.items()}
    pr = {x.offset: x for x in c["polling rate"].fields}
    assert pr[2].kind == "lookup" and pr[2].table == {float(k): v for k, v in POLL.items()}
    col = {x.offset: x for x in c["color"].fields}
    assert [(col[i].kind, col[i].index) for i in (2, 3, 4)] == [("value", 0), ("value", 1), ("value", 2)]
    assert c["color"].encode(1, 2, 3) == bytes([5, 0, 1, 2, 3])
    assert all(cmd.confidence == 1.0 for cmd in p.commands)
