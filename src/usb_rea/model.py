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

    @property
    def values(self) -> list[float]:
        return split_values(self.label)[1]


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


def split_values(label: str) -> tuple[str, list[float]]:
    """'color 255, 24, 0' -> ('color', [255, 24, 0]); falls back to split_label for one/zero values."""
    import re
    toks = [t for t in re.split(r"[\s,=:;/]+", label.strip()) if t]
    name, nums = [], []
    for t in toks:
        m = re.fullmatch(r"(-?\d+(?:\.\d+)?)%?", t)
        if m and name:
            nums.append(float(m.group(1)))
        elif nums:
            break
        else:
            name.append(t)
    if len(nums) >= 2 and len(name) + len(nums) == len(toks):
        return " ".join(name).lower(), nums
    n, v = split_label(label)
    return n, [] if v is None else [v]


def is_observation(label: str) -> bool:
    """'seen rpm 1180' notes what the vendor app displayed; it is not an action."""
    import re
    return bool(re.match(r"\s*seen\b", label, re.I))


def split_observation(label: str) -> list[tuple[str, float | str]]:
    """'seen rpm 1180, temp 34°C' -> [('rpm', 1180.0), ('temp', 34.0)]; [] for other labels.
    On/off states count as 1/0: 'seen pump on, alarm off' -> [('pump', 1.0), ('alarm', 0.0)].
    A word as the last of two or more words of a part is a mode or other enum value, kept as text:
    'seen mode turbo' -> [('mode', 'turbo')], 'seen rpm 1180 fan mode quiet' -> [..., ('fan mode', 'quiet')].
    A comma between digits is a thousands separator before exactly three digits ('1,180' -> 1180) and a
    decimal comma otherwise ('41,5' -> 41.5); a comma followed by a space still separates parts."""
    import re
    if not is_observation(label):
        return []
    body = label.strip()[4:]
    # numbers as Windows apps print them in many locales: '1,180 rpm' (thousands), '41,5 °C' (decimal)
    body = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", body)
    body = re.sub(r"(?<=\d),(?=\d)", ".", body)
    out = []
    for part in re.split(r"[,;]+", body):
        name = []
        for t in re.split(r"[\s=:]+", part.strip()):
            v = re.fullmatch(r"(-?\d+(?:\.\d+)?)(?:%|°?[a-zA-Z]{0,3})", t)
            state = {"on": 1.0, "off": 0.0, "true": 1.0, "false": 0.0, "yes": 1.0, "no": 0.0}.get(t.lower())
            if (v or state is not None) and name:
                out.append((" ".join(name).lower(), float(v.group(1)) if v else state))
                name = []
            elif t and not v:
                name.append(t)
        if len(name) >= 2:
            out.append((" ".join(name[:-1]).lower(), name[-1].lower()))
    return out
