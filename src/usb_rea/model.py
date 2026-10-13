"""Core data model."""
from __future__ import annotations
from dataclasses import dataclass, field

XFER_NAMES = {0: "iso", 1: "interrupt", 2: "control", 3: "bulk"}


@dataclass
class Transfer:
    """One USB data movement seen in a capture (an OUT submission or an IN completion)."""
    frame: int            # 1-based frame number in the capture (matches Wireshark)
    ts: float             # seconds since epoch
    bus: int
    device: int
    endpoint: int         # includes direction bit 0x80 for IN
    xfer_type: int        # 0 iso, 1 interrupt, 2 control, 3 bulk
    setup: bytes | None   # 8-byte setup packet for control transfers
    data: bytes

    @property
    def is_in(self) -> bool:
        return bool(self.endpoint & 0x80)

    @property
    def is_out(self) -> bool:
        return not self.is_in

    @property
    def kind(self) -> str:
        return XFER_NAMES.get(self.xfer_type, str(self.xfer_type))

    def key(self) -> tuple:
        """Channel identity used to align messages across actions."""
        s = self.setup[:4].hex() if self.setup else ""
        return (self.device, self.endpoint, self.xfer_type, s)


@dataclass
class Action:
    label: str
    start: float
    end: float
    transfers: list[Transfer] = field(default_factory=list)

    @property
    def name(self) -> str:
        return split_label(self.label)[0]

    @property
    def value(self) -> float | None:
        return split_label(self.label)[1]


def split_label(label: str) -> tuple[str, float | None]:
    """'brightness 50%' -> ('brightness', 50.0); 'power on' -> ('power', 1.0); 'reset' -> ('reset', None)."""
    import re
    label = label.strip()
    m = re.match(r"^(.*?)[\s=:]+(-?\d+(?:\.\d+)?)\s*%?$", label)
    if m:
        return m.group(1).strip().lower(), float(m.group(2))
    words = label.lower().split()
    if len(words) >= 2 and words[-1] in ("on", "off", "true", "false", "yes", "no"):
        return " ".join(words[:-1]), 1.0 if words[-1] in ("on", "true", "yes") else 0.0
    return label.lower(), None
