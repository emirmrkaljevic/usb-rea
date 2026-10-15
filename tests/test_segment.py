from usb_rea.cli import main
from usb_rea.pipeline import analyze
from usb_rea.synth import make_capture, FAN_ACTIONS, encode_fan


def test_labels_without_markers_match_marked_analysis(tmp_path):
    cap, marks = make_capture(tmp_path / "fan.pcap", device="fan")
    marks.unlink()  # e.g. a plain Wireshark/USBPcap capture
    p = analyze(cap, labels=FAN_ACTIONS)
    c = {c.name: c for c in p.commands}
    assert set(c) == {"fan", "color", "mode"}
    assert all(x.confidence == 1.0 for x in p.commands)
    assert c["fan"].encode(3100, seq=7) == encode_fan("fan", [3100], 7)


def test_cli_labels_file(tmp_path, capsys):
    cap, marks = make_capture(tmp_path / "lamp.pcap")
    marks.unlink()
    lf = tmp_path / "labels.txt"
    lf.write_text("# clicked in this order\nbrightness 0%\nbrightness 25%\nbrightness 50%\nbrightness 75%\n"
                  "brightness 100%\npower off\npower on\nhue 0\nhue 120\nhue 240\n")
    assert main(["report", str(cap), "--labels", str(lf)]) == 0
    assert "sum8" in capsys.readouterr().out


def test_too_many_labels(tmp_path):
    import pytest
    cap, _ = make_capture(tmp_path / "lamp.pcap", actions=["brightness 0%", "brightness 50%"])
    with pytest.raises(ValueError):
        analyze(cap, labels=["a 1", "a 2", "a 3"])
