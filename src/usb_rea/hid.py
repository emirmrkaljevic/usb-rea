"""HID report descriptor decoder.

Turns the raw report descriptor (GET_DESCRIPTOR type 0x22, or a hex string from
`lsusb -v`, `usbhid-dump`, `/sys/class/hidraw/*/device/report_descriptor`) into
reports and fields, so captured SET_REPORT / interrupt payloads can be mapped to
named, bit-exact fields.  Pure Python, follows HID 1.11 section 6.2.2.
"""
from __future__ import annotations
from dataclasses import dataclass, field

MAIN = {0x8: "Input", 0x9: "Output", 0xB: "Feature", 0xA: "Collection", 0xC: "End Collection"}
GLOBAL = {0x0: "Usage Page", 0x1: "Logical Minimum", 0x2: "Logical Maximum", 0x3: "Physical Minimum",
          0x4: "Physical Maximum", 0x5: "Unit Exponent", 0x6: "Unit", 0x7: "Report Size",
          0x8: "Report ID", 0x9: "Report Count", 0xA: "Push", 0xB: "Pop"}
LOCAL = {0x0: "Usage", 0x1: "Usage Minimum", 0x2: "Usage Maximum", 0x3: "Designator Index",
         0x4: "Designator Minimum", 0x5: "Designator Maximum", 0x7: "String Index",
         0x8: "String Minimum", 0x9: "String Maximum", 0xA: "Delimiter"}
COLLECTIONS = {0: "Physical", 1: "Application", 2: "Logical", 3: "Report", 4: "Named Array",
               5: "Usage Switch", 6: "Usage Modifier"}
PAGES = {0x01: "Generic Desktop", 0x02: "Simulation", 0x05: "Game", 0x06: "Generic Device",
         0x07: "Keyboard/Keypad", 0x08: "LED", 0x09: "Button", 0x0A: "Ordinal", 0x0B: "Telephony",
         0x0C: "Consumer", 0x0D: "Digitizer", 0x0F: "PID", 0x14: "Auxiliary Display",
         0x20: "Sensor", 0x59: "Lighting And Illumination", 0x84: "Power Device", 0x85: "Battery System"}
USAGES = {
    0x01: {0x01: "Pointer", 0x02: "Mouse", 0x04: "Joystick", 0x05: "Game Pad", 0x06: "Keyboard",
           0x07: "Keypad", 0x08: "Multi-axis Controller", 0x30: "X", 0x31: "Y", 0x32: "Z", 0x33: "Rx",
           0x34: "Ry", 0x35: "Rz", 0x36: "Slider", 0x37: "Dial", 0x38: "Wheel", 0x39: "Hat Switch",
           0x80: "System Control", 0x81: "System Power Down", 0x82: "System Sleep", 0x83: "System Wake Up"},
    0x0C: {0x01: "Consumer Control", 0xB5: "Scan Next Track", 0xB6: "Scan Previous Track",
           0xB7: "Stop", 0xCD: "Play/Pause", 0xE2: "Mute", 0xE9: "Volume Increment",
           0xEA: "Volume Decrement", 0x238: "AC Pan"},
    0x08: {0x01: "Num Lock", 0x02: "Caps Lock", 0x03: "Scroll Lock", 0x04: "Compose", 0x05: "Kana"},
}
REPORT_TYPES = {1: "Input", 2: "Output", 3: "Feature"}


def page_name(page: int) -> str:
    if page >= 0xFF00:
        return f"Vendor 0x{page:04X}"
    return PAGES.get(page, f"Page 0x{page:02X}")


def usage_name(page: int, usage: int) -> str:
    if page == 0x09:
        return f"Button {usage}"
    if page == 0x0A:
        return f"Instance {usage}"
    return USAGES.get(page, {}).get(usage, f"0x{usage:02X}")


@dataclass
class Item:
    offset: int
    kind: str          # "main" | "global" | "local" | "long"
    tag: int
    data: bytes

    @property
    def uvalue(self) -> int:
        return int.from_bytes(self.data, "little") if self.data else 0

    @property
    def svalue(self) -> int:
        return int.from_bytes(self.data, "little", signed=True) if self.data else 0

    @property
    def name(self) -> str:
        table = {"main": MAIN, "global": GLOBAL, "local": LOCAL}.get(self.kind, {})
        return table.get(self.tag, f"{self.kind} tag 0x{self.tag:X}")


def items(desc: bytes) -> list[Item]:
    out, i = [], 0
    while i < len(desc):
        p = desc[i]
        if p == 0xFE:  # long item
            if i + 2 >= len(desc):
                raise ValueError(f"truncated long item at byte {i}")
            size, tag = desc[i + 1], desc[i + 2]
            out.append(Item(i, "long", tag, bytes(desc[i + 3:i + 3 + size])))
            i += 3 + size
            continue
        size = (0, 1, 2, 4)[p & 3]
        kind = ("main", "global", "local", "reserved")[(p >> 2) & 3]
        if i + 1 + size > len(desc):
            raise ValueError(f"truncated item 0x{p:02x} at byte {i}")
        out.append(Item(i, kind, p >> 4, bytes(desc[i + 1:i + 1 + size])))
        i += 1 + size
    return out


@dataclass
class Field:
    report_type: str           # Input | Output | Feature
    report_id: int             # 0 when the descriptor uses no report IDs
    bit_offset: int            # offset inside the report payload, excluding the report ID byte
    size: int                  # bits per element
    count: int
    usage_page: int
    usages: list[int]          # one per element for variables; the usage range for arrays
    logical_min: int
    logical_max: int
    flags: int
    collection: str = ""

    @property
    def constant(self) -> bool:
        return bool(self.flags & 1)

    @property
    def variable(self) -> bool:
        return bool(self.flags & 2)

    @property
    def relative(self) -> bool:
        return bool(self.flags & 4)

    def label(self, i: int = 0) -> str:
        if self.constant:
            return "padding"
        if not self.usages:
            return f"{page_name(self.usage_page)} (no usage)"
        if not self.variable:
            lo, hi = self.usages[0], self.usages[-1]
            return (f"{page_name(self.usage_page)} array "
                    f"[{usage_name(self.usage_page, lo)}..{usage_name(self.usage_page, hi)}]")
        u = self.usages[min(i, len(self.usages) - 1)]
        return f"{page_name(self.usage_page)}: {usage_name(self.usage_page, u)}"

    def describe(self) -> str:
        bits = f"bits {self.bit_offset}..{self.bit_offset + self.size * self.count - 1}"
        what = self.label()
        if self.variable and not self.constant and self.count > 1 and len(set(self.usages)) > 1:
            what = f"{what} .. {usage_name(self.usage_page, self.usages[-1])}"
        attrs = ("Const" if self.constant else "Data", "Var" if self.variable else "Array",
                 "Rel" if self.relative else "Abs")
        return (f"{bits}: {what} ({self.count}x{self.size} bit, logical {self.logical_min}..{self.logical_max}, "
                f"{','.join(attrs)})")


@dataclass
class Report:
    report_type: str
    report_id: int
    fields: list[Field] = field(default_factory=list)

    @property
    def bits(self) -> int:
        return max((f.bit_offset + f.size * f.count for f in self.fields), default=0)

    @property
    def length(self) -> int:
        """Bytes on the wire, including the report ID byte when IDs are used."""
        return (self.bits + 7) // 8 + (1 if self.report_id else 0)

    @property
    def vendor(self) -> bool:
        return any(f.usage_page >= 0xFF00 for f in self.fields if not f.constant)

    def title(self) -> str:
        rid = f"id 0x{self.report_id:02X}" if self.report_id else "no id"
        page = next((page_name(f.usage_page) for f in self.fields if not f.constant), "padding only")
        return f"{self.report_type} report ({rid}, {self.length} bytes, {page})"


@dataclass
class Descriptor:
    raw: bytes
    items: list[Item]
    reports: list[Report]
    top_usages: list[str]

    @property
    def uses_report_ids(self) -> bool:
        return any(r.report_id for r in self.reports)

    def report(self, report_type: str, report_id: int = 0) -> Report | None:
        for r in self.reports:
            if r.report_type == report_type and r.report_id == report_id:
                return r
        return None

    def to_dict(self) -> dict:
        return {"length": len(self.raw), "top_level": self.top_usages, "uses_report_ids": self.uses_report_ids,
                "reports": [{"type": r.report_type, "id": r.report_id, "length": r.length, "vendor": r.vendor,
                             "fields": [f.describe() for f in r.fields]} for r in self.reports]}


def parse(desc: bytes | str) -> Descriptor:
    """Parse a report descriptor (bytes, or hex with optional spaces/0x/commas)."""
    if isinstance(desc, str):
        desc = bytes.fromhex(desc.replace("0x", "").replace(",", " ").replace("\n", " "))
    its = items(desc)
    g = {"page": 0, "lmin": 0, "lmax": 0, "size": 0, "count": 0, "id": 0}
    stack: list[dict] = []
    local: dict = {"usages": [], "min": None, "max": None}
    reports: dict[tuple[str, int], Report] = {}
    colls: list[str] = []
    top: list[str] = []

    def full(u: Item) -> tuple[int, int]:
        if len(u.data) == 4:
            return u.uvalue >> 16, u.uvalue & 0xFFFF
        return g["page"], u.uvalue

    for it in its:
        if it.kind == "global":
            if it.tag == 0x0:
                g["page"] = it.uvalue
            elif it.tag == 0x1:
                g["lmin"] = it.svalue
            elif it.tag == 0x2:
                # logical max is read as signed only when logical min is negative (what Linux hid-core does)
                g["lmax"] = it.svalue if g["lmin"] < 0 else it.uvalue
            elif it.tag == 0x7:
                g["size"] = it.uvalue
            elif it.tag == 0x8:
                g["id"] = it.uvalue
            elif it.tag == 0x9:
                g["count"] = it.uvalue
            elif it.tag == 0xA:
                stack.append(dict(g))
            elif it.tag == 0xB and stack:
                g = stack.pop()
        elif it.kind == "local":
            if it.tag == 0x0:
                local["usages"].append(full(it))
            elif it.tag == 0x1:
                local["min"] = full(it)
            elif it.tag == 0x2:
                local["max"] = full(it)
        elif it.kind == "main":
            if it.tag == 0xA:
                u = local["usages"][0] if local["usages"] else None
                name = f"{page_name(u[0])}: {usage_name(*u)}" if u else "?"
                kind = COLLECTIONS.get(it.uvalue, f"0x{it.uvalue:02X}")
                if not colls:
                    top.append(name)
                colls.append(f"{name} ({kind})")
            elif it.tag == 0xC:
                if colls:
                    colls.pop()
            elif it.tag in (0x8, 0x9, 0xB):
                rtype = MAIN[it.tag]
                rep = reports.setdefault((rtype, g["id"]), Report(rtype, g["id"]))
                usages = list(local["usages"])
                if local["min"] is not None and local["max"] is not None:
                    pg = local["min"][0]
                    usages += [(pg, u) for u in range(local["min"][1], local["max"][1] + 1)]
                page = usages[0][0] if usages else g["page"]
                fld = Field(rtype, g["id"], rep.bits, g["size"], g["count"], page,
                            [u for _, u in usages], g["lmin"], g["lmax"], it.uvalue,
                            colls[-1] if colls else "")
                if fld.variable and fld.usages and len(fld.usages) < fld.count:
                    fld.usages += [fld.usages[-1]] * (fld.count - len(fld.usages))
                rep.fields.append(fld)
            local = {"usages": [], "min": None, "max": None}
    return Descriptor(bytes(desc), its, list(reports.values()), top)


def _bits(data: bytes, offset: int, size: int) -> int:
    v = int.from_bytes(data, "little")
    return (v >> offset) & ((1 << size) - 1)


def decode(desc: Descriptor, report_type: str, data: bytes) -> list[tuple[str, int]]:
    """Decode one report payload into (field label, value) pairs. Padding is skipped."""
    rid = data[0] if desc.uses_report_ids and data else 0
    body = data[1:] if rid else data
    rep = desc.report(report_type, rid)
    if rep is None:
        raise KeyError(f"no {report_type} report with id {rid} in descriptor")
    out = []
    for f in rep.fields:
        if f.constant:
            continue
        for i in range(f.count):
            raw = _bits(body, f.bit_offset + i * f.size, f.size)
            if f.logical_min < 0 and raw & (1 << (f.size - 1)):
                raw -= 1 << f.size
            if f.variable:
                out.append((f.label(i), raw))
            elif raw:
                u = (f.usages[0] + raw - f.logical_min) if f.usages else raw
                out.append((f"{page_name(f.usage_page)} usage", u))
    return out


def dump(desc: Descriptor) -> str:
    """hid-tools style listing: one line per item, with byte offsets."""
    lines, depth, page = [], 0, 0
    for it in desc.items:
        if it.kind == "global" and it.tag == 0:
            page = it.uvalue
        if it.kind == "main" and it.tag == 0xC:
            depth = max(0, depth - 1)
        raw = desc.raw[it.offset:it.offset + 1 + len(it.data)].hex(" ")
        val = ""
        if it.data:
            if it.kind == "global" and it.tag == 0:
                val = page_name(it.uvalue)
            elif it.kind == "main" and it.tag == 0xA:
                val = COLLECTIONS.get(it.uvalue, hex(it.uvalue))
            elif it.kind == "main":
                val = ",".join(("Const" if it.uvalue & 1 else "Data", "Var" if it.uvalue & 2 else "Array",
                                "Rel" if it.uvalue & 4 else "Abs"))
            elif it.kind == "local" and it.tag in (0, 1, 2):
                pg, u = (it.uvalue >> 16, it.uvalue & 0xFFFF) if len(it.data) == 4 else (page, it.uvalue)
                val = usage_name(pg, u)
            elif it.kind == "global" and it.tag in (1, 2, 3, 4):
                val = str(it.svalue)
            else:
                val = str(it.uvalue)
        lines.append(f"{it.offset:4d}  {raw:<15s} {'  ' * depth}{it.name}" + (f" ({val})" if val else ""))
        if it.kind == "main" and it.tag == 0xA:
            depth += 1
    return "\n".join(lines)


def from_transfers(transfers) -> dict[tuple[int, int], bytes]:
    """Find HID report descriptors in a capture: {(device, interface): descriptor bytes}."""
    found: dict[tuple[int, int], bytes] = {}
    pending: dict[int, int] = {}
    for t in transfers:
        if t.xfer_type != 2:
            continue
        if t.setup and t.setup[0] == 0x81 and t.setup[1] == 6 and t.setup[3] == 0x22:
            pending[t.device] = t.setup[4] | (t.setup[5] << 8)
        elif t.device in pending and t.is_in and t.data and not t.setup:
            found[(t.device, pending.pop(t.device))] = t.data
    return found


def match(desc: Descriptor, setup: bytes | None, endpoint: int, data: bytes) -> Report | None:
    """Which report a host->device message is, from its SET_REPORT setup or interrupt OUT payload."""
    if setup:
        if setup[0] & 0x60 == 0x20 and setup[1] == 0x09:  # class request SET_REPORT
            rtype = REPORT_TYPES.get(setup[3])
            return desc.report(rtype, setup[2]) if rtype else None
        return None
    if endpoint & 0x80 == 0:
        rid = data[0] if desc.uses_report_ids and data else 0
        return desc.report("Output", rid)
    return None
