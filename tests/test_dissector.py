"""Generated Wireshark dissector: Lua syntax, checksum helpers, and a real tshark run when available."""
import shutil
import subprocess

import pytest

from usb_rea.checksums import CHECKSUMS, compute
from usb_rea.cli import main
from usb_rea.dissector import _HELPERS, _LUA_CHECKSUMS, generate
from usb_rea.pipeline import analyze
from usb_rea.synth import encode, make_capture

LUA = next((shutil.which(n) for n in ("lua5.4", "lua5.3", "lua5.2", "lua") if shutil.which(n)), None)
TSHARK = shutil.which("tshark")


def _tshark(lua, cap, *args):
    out = subprocess.run([TSHARK, "-X", f"lua_script:{lua}", "-r", str(cap), "-Y", "usbrea", *args],
                         capture_output=True, text=True, timeout=60)
    assert "Lua: Error" not in out.stderr, out.stderr
    return out.stdout


def _info(lua, cap):
    # -T fields reads _ws.col.info before postdissectors run, so print the Info column itself
    return _tshark(lua, cap, "-o", 'gui.column.format:"Info","%i"').splitlines()


def test_every_checksum_has_a_lua_version():
    assert set(_LUA_CHECKSUMS) == set(CHECKSUMS)


@pytest.mark.skipif(LUA is None, reason="no lua interpreter")
def test_lua_checksums_match_python():
    data = list(b"123456789") + [0xFF, 0x00, 0x80]
    lua = _HELPERS + "local d = {" + ",".join(map(str, data)) + "}\n"
    for name, expr in _LUA_CHECKSUMS.items():
        lua += f'print("{name}", math.floor({expr}))\n'
    out = subprocess.run([LUA, "-"], input=lua, capture_output=True, text=True, check=True).stdout
    got = dict(line.split("\t") for line in out.split("\n") if line)
    for name in CHECKSUMS:
        assert int(got[name]) == compute(name, bytes(data)), name


@pytest.mark.skipif(LUA is None, reason="no lua interpreter")
@pytest.mark.parametrize("device,transport", [("lamp", "bulk"), ("lamp", "control"), ("fan", "bulk"), ("dial", "bulk")])
def test_generated_lua_compiles(tmp_path, device, transport):
    cap, _ = make_capture(tmp_path / f"{device}.pcap", device=device, transport=transport)
    path = tmp_path / "d.lua"
    path.write_text(generate(analyze(cap)))
    subprocess.run([LUA, "-e", f"assert(loadfile('{path}'))"], check=True)


def test_cli_dissector(tmp_path, capsys):
    cap, _ = make_capture(tmp_path / "lamp.pcap")
    out = tmp_path / "lamp.lua"
    assert main(["dissector", str(cap), "-n", "mylamp", "-o", str(out)]) == 0
    src = out.read_text()
    assert "register_postdissector" in src and '"mylamp.brightness.value"' in src


@pytest.mark.skipif(TSHARK is None, reason="tshark not installed")
@pytest.mark.parametrize("transport", ["bulk", "control"])
def test_tshark_labels_lamp_commands(tmp_path, transport):
    cap, _ = make_capture(tmp_path / "lamp.pcap", transport=transport)
    lua = tmp_path / "lamp.lua"
    lua.write_text(generate(analyze(cap)))
    assert _info(lua, cap) == ["brightness 0", "brightness 25", "brightness 50", "brightness 75",
                               "brightness 100", "power 0", "power 1", "hue 0", "hue 120", "hue 240"]
    ok = _tshark(lua, cap, "-T", "fields", "-e", "usbrea.checksum_ok").split()
    assert ok == ["True"] * 10


@pytest.mark.skipif(TSHARK is None, reason="tshark not installed")
def test_tshark_decodes_fan_and_dial(tmp_path):
    for device, expect in (("fan", ["fan 2650", "color 0 128 255", "mode 3"]),
                           ("dial", ["position 2309737967", "level 15"])):
        cap, _ = make_capture(tmp_path / f"{device}.pcap", device=device)
        lua = tmp_path / f"{device}.lua"
        lua.write_text(generate(analyze(cap)))
        info = _info(lua, cap)
        assert set(expect) <= set(info), info


@pytest.mark.skipif(TSHARK is None, reason="tshark not installed")
def test_tshark_flags_bad_checksum(tmp_path):
    cap, _ = make_capture(tmp_path / "lamp.pcap")
    lua = tmp_path / "lamp.lua"
    lua.write_text(generate(analyze(cap)))
    good = encode("brightness", 50)
    raw = cap.read_bytes()
    assert raw.count(good) == 1
    cap.write_bytes(raw.replace(good, good[:-1] + bytes([good[-1] ^ 0xFF])))
    info = _info(lua, cap)
    assert "brightness 50 [bad checksum]" in info
    assert _tshark(lua, cap, "-T", "fields", "-e", "usbrea.checksum_ok").split().count("False") == 1
