import argparse
from . import __version__

def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="usb-rea", description="Reverse Engineer any USB gadget")
    p.add_argument("--version", action="version", version=__version__)
    p.parse_args(argv)
    p.print_help()
    return 0
