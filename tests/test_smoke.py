import usb_rea
from usb_rea.cli import main

def test_version():
    assert usb_rea.__version__

def test_cli_help():
    assert main([]) == 0
