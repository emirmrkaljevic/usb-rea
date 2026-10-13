"""Send a packet to a real device. Always requires explicit confirmation."""
from __future__ import annotations


def replay(vid: int, pid: int, endpoint: int, data: bytes, setup: bytes | None = None,
           confirm: bool = False) -> str:
    if not confirm:
        raise PermissionError("replay sends data to real hardware; pass confirm=True (CLI: --yes) after reviewing it")
    import usb.core
    dev = usb.core.find(idVendor=vid, idProduct=pid)
    if dev is None:
        raise RuntimeError(f"device {vid:04x}:{pid:04x} not found")
    if setup:
        bm, req = setup[0], setup[1]
        wv, wi = setup[2] | setup[3] << 8, setup[4] | setup[5] << 8
        n = dev.ctrl_transfer(bm, req, wv, wi, data)
    else:
        n = dev.write(endpoint, data)
    return f"sent {n} bytes"
