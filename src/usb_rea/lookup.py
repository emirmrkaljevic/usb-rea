"""Look up a USB VID:PID before capturing: has someone already documented this device's protocol?

Offline first. The answer comes from a small table of devices whose protocol an open-source project
already implements (the same projects usb-rea is validated against), plus vendor and product names
from a local usb.ids file when one is installed (usbutils/hwdata ship it). `online=True` also asks
OpenDeviceDB (https://opendevicedb.org, its read-only static API); without a network that part just
reports the error and the offline answer stays as it is.

A matching USB ID is a hint, not proof: vendors reuse IDs across revisions and generic chips
(a WCH serial bridge, for example) carry the same ID in unrelated products.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

LIQUIDCTL = "https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/"
RIVALCFG = "https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/"
TURING = "https://github.com/mathoudebine/turing-smart-screen-python"
THERMALRIGHT = "https://github.com/rejeb/linux-thermalright-lcd-control"
DOCS = "https://github.com/emirmrkaljevic/usb-rea/blob/main/docs/"

VENDORS = {
    0x0416: "Winbond Electronics Corp.",
    0x0B05: "ASUSTek Computer, Inc.",
    0x1038: "SteelSeries ApS",
    0x1A86: "QinHeng Electronics",
    0x1B1C: "Corsair",
    0x1E71: "NZXT",
}


def _p(name, url, note=""):
    return {"project": name, "url": url, "note": note}


# (vid, pid) -> name, projects that implement or document the protocol, and limits worth knowing
KNOWN: dict[tuple[int, int], dict] = {
    (0x1E71, 0x170E): {"name": "NZXT Kraken X (X42, X52, X62 or X72)", "projects": [
        _p("liquidctl", LIQUIDCTL + "kraken2.py", "fan/pump duty, lighting, status"),
        _p("usb-rea validation", DOCS + "VALIDATION.md", "fan duty command recovered byte for byte")]},
    (0x1E71, 0x1715): {"name": "NZXT Kraken M22", "projects": [_p("liquidctl", LIQUIDCTL + "kraken2.py")]},
    (0x1E71, 0x2007): {"name": "NZXT Kraken X (X53, X63 or X73)", "projects": [_p("liquidctl", LIQUIDCTL + "kraken3.py")]},
    (0x1E71, 0x2014): {"name": "NZXT Kraken X (X53, X63 or X73)", "projects": [_p("liquidctl", LIQUIDCTL + "kraken3.py")]},
    (0x1E71, 0x3008): {"name": "NZXT Kraken Z (Z53, Z63 or Z73)", "projects": [
        _p("liquidctl", LIQUIDCTL + "kraken3.py", "includes the 320x320 LCD")]},
    (0x1E71, 0x300E): {"name": "NZXT Kraken 2023", "projects": [_p("liquidctl", LIQUIDCTL + "kraken3.py")]},
    (0x1E71, 0x3012): {"name": "NZXT Kraken 2024 Elite RGB", "projects": [_p("liquidctl", LIQUIDCTL + "kraken3.py")]},
    (0x1E71, 0x3014): {"name": "NZXT Kraken 2024 Plus", "projects": [_p("liquidctl", LIQUIDCTL + "kraken3.py")]},
    (0x1B1C, 0x0C18): {"name": "Corsair Hydro H100i Platinum", "projects": [
        _p("liquidctl", LIQUIDCTL + "hydro_platinum.py"),
        _p("usb-rea case study", DOCS + "case-study-hydro-platinum.md", "CRC8 and sequence counter recovered")]},
    (0x1B1C, 0x0C19): {"name": "Corsair Hydro H100i Platinum SE", "projects": [_p("liquidctl", LIQUIDCTL + "hydro_platinum.py")]},
    (0x1B1C, 0x0C17): {"name": "Corsair Hydro H115i Platinum", "projects": [_p("liquidctl", LIQUIDCTL + "hydro_platinum.py")]},
    (0x1B1C, 0x0C29): {"name": "Corsair Hydro H60i Pro XT", "projects": [_p("liquidctl", LIQUIDCTL + "hydro_platinum.py")]},
    (0x1B1C, 0x0C20): {"name": "Corsair Hydro H100i Pro XT", "projects": [_p("liquidctl", LIQUIDCTL + "hydro_platinum.py")]},
    (0x1B1C, 0x0C21): {"name": "Corsair Hydro H115i Pro XT", "projects": [_p("liquidctl", LIQUIDCTL + "hydro_platinum.py")]},
    (0x1B1C, 0x0C22): {"name": "Corsair Hydro H150i Pro XT", "projects": [_p("liquidctl", LIQUIDCTL + "hydro_platinum.py")]},
    (0x1B1C, 0x0C35): {"name": "Corsair iCUE H100i Elite RGB", "projects": [_p("liquidctl", LIQUIDCTL + "hydro_platinum.py")]},
    (0x1B1C, 0x0C36): {"name": "Corsair iCUE H115i Elite RGB", "projects": [_p("liquidctl", LIQUIDCTL + "hydro_platinum.py")]},
    (0x1B1C, 0x0C37): {"name": "Corsair iCUE H150i Elite RGB", "projects": [_p("liquidctl", LIQUIDCTL + "hydro_platinum.py")]},
    (0x1038, 0x1702): {"name": "SteelSeries Rival 100", "projects": [
        _p("rivalcfg", RIVALCFG + "rival100.py", "DPI, polling rate, RGB"),
        _p("usb-rea validation", DOCS + "VALIDATION.md", "DPI/polling lookup tables recovered")]},
    (0x1038, 0x170A): {"name": "SteelSeries Rival 100 (Dell China)", "projects": [_p("rivalcfg", RIVALCFG + "rival100.py")]},
    (0x1038, 0x170B): {"name": "SteelSeries Rival 100 Dota 2 Edition (retail)", "projects": [_p("rivalcfg", RIVALCFG + "rival100.py")]},
    (0x1038, 0x170C): {"name": "SteelSeries Rival 100 Dota 2 Edition (Lenovo)", "projects": [_p("rivalcfg", RIVALCFG + "rival100.py")]},
    (0x1038, 0x1814): {"name": "SteelSeries Rival 105", "projects": [_p("rivalcfg", RIVALCFG + "rival100.py")]},
    (0x0B05, 0x1C7B): {"name": "ASUS TUF Gaming LC III LCD", "projects": [
        _p("usb-rea case study", DOCS + "case-study-asus-tuf-lc3.md",
           "brightness command and JPEG stream from one real capture; not a full driver")]},
    (0x1A86, 0x5722): {"name": "Turing Smart Screen 3.5\" (rev A) / XuanFang (rev B)", "projects": [
        _p("turing-smart-screen-python", TURING, "serial protocol for revisions A and B")],
        "limits": "generic WCH serial bridge ID; the project tells revisions apart by the USB serial "
                  "number (USB35INCHIPSV2 is rev A), and unrelated devices use this ID too"},
    (0x0416, 0x5302): {"name": "Thermalright LCD (ChiZhu, 320x240, HID)", "projects": [
        _p("linux-thermalright-lcd-control", THERMALRIGHT)],
        "limits": "Winbond/Nuvoton generic ID used by other products as well"},
    (0x87AD, 0x70DB): {"name": "Thermalright LCD (ChiZhu, 320/480/640 variants)", "projects": [
        _p("linux-thermalright-lcd-control", THERMALRIGHT)]},
    (0x0416, 0x5408): {"name": "Thermalright LCD (LY)", "projects": [_p("linux-thermalright-lcd-control", THERMALRIGHT)]},
    (0x0416, 0x5409): {"name": "Thermalright LCD (LY)", "projects": [_p("linux-thermalright-lcd-control", THERMALRIGHT)]},
}

NOTE = "A matching USB ID alone does not prove your unit speaks the same protocol; check the project's notes."

USB_IDS_PATHS = ("/usr/share/hwdata/usb.ids", "/usr/share/misc/usb.ids", "/usr/share/usb.ids",
                 "/var/lib/usbutils/usb.ids", "/usr/local/share/hwdata/usb.ids")

ODB_API = "https://opendevicedb.org/api"


def parse_id(text: str) -> tuple[int, int]:
    """'1e71:170e', '0x1e71:0x170e' or '1e71 170e' -> (0x1e71, 0x170e)."""
    m = re.fullmatch(r"\s*(?:0x)?([0-9a-fA-F]{1,4})\s*[:\s]\s*(?:0x)?([0-9a-fA-F]{1,4})\s*", text)
    if not m:
        raise ValueError(f"not a VID:PID: {text!r} (expected e.g. 1e71:170e)")
    return int(m[1], 16), int(m[2], 16)


def usb_ids_names(text: str, vid: int, pid: int) -> tuple[str | None, str | None]:
    """Vendor and product name for vid:pid from the contents of a usb.ids file."""
    vendor = product = None
    v, p = f"{vid:04x}", f"{pid:04x}"
    in_vendor = False
    for line in text.splitlines():
        if not line or line[0] == "#":
            continue
        if line[0] == "\t":
            if in_vendor and line[1] != "\t" and line[1:5].lower() == p and line[5:7] == "  ":
                product = line[7:].strip()
                break
            continue
        if in_vendor or line.startswith("C "):  # the vendor's block ended, or the class list began
            break
        if line[:4].lower() == v and line[4:6] == "  ":
            vendor, in_vendor = line[6:].strip(), True
    return vendor, product


def find_usb_ids(path: str | Path | None = None) -> Path | None:
    for c in ([path] if path else [os.environ.get("USB_IDS"), *USB_IDS_PATHS]):
        if c and Path(c).is_file():
            return Path(c)
    return None


def _fetch(url: str, timeout: float = 15.0) -> bytes:
    from urllib.request import Request, urlopen
    with urlopen(Request(url, headers={"User-Agent": "usb-rea lookup"}), timeout=timeout) as r:
        return r.read()


def opendevicedb(vid: int, pid: int, fetch=None) -> dict:
    """Records in OpenDeviceDB whose USB identifiers include vid:pid. Never raises: errors are returned."""
    want = f"{vid:04x}:{pid:04x}"
    fetch = fetch or _fetch
    try:
        index = json.loads(fetch(f"{ODB_API}/index.json"))
        hits = [r for r in index if want in [u.lower() for u in (r.get("identifiers") or {}).get("usb", [])]]
        out = []
        for r in hits[:5]:
            rec = {"id": r["id"], "vendor": r.get("vendor"), "model": r.get("model"),
                   "status": r.get("status"), "sources": r.get("sources", []),
                   "url": f"https://opendevicedb.org/devices/{r['id']}", "projects": []}
            try:
                full = json.loads(fetch(f"{ODB_API}/devices/{r['id']}.json"))
                rec["projects"] = [{"project": p.get("name"), "url": p.get("url")} for p in full.get("projects", [])]
            except Exception:  # the summary from the index is still useful
                pass
            out.append(rec)
        return {"source": ODB_API, "records": out}
    except Exception as e:
        return {"source": ODB_API, "error": f"{type(e).__name__}: {e}", "records": []}


def lookup(vid: int, pid: int, online: bool = False, usb_ids: str | Path | None = None, fetch=None) -> dict:
    """What is known about vid:pid, offline unless `online` (OpenDeviceDB) is set."""
    known = KNOWN.get((vid, pid))
    out = {"id": f"{vid:04x}:{pid:04x}", "vendor": VENDORS.get(vid), "product": known["name"] if known else None,
           "names_from": "usb-rea" if known or vid in VENDORS else None,
           "status": "documented" if known else "unknown",
           "projects": list(known["projects"]) if known else [], "limits": (known or {}).get("limits"),
           "same_vendor": sorted({p["project"] for (v, _), k in KNOWN.items() if v == vid and k is not known
                                  for p in k["projects"] if not p["project"].startswith("usb-rea")}),
           "note": NOTE}
    ids = find_usb_ids(usb_ids)
    if ids:
        v, p = usb_ids_names(ids.read_text(errors="replace"), vid, pid)
        if v or p:
            out["vendor"], out["product"] = v or out["vendor"], out["product"] or p
            out["usb_ids"] = {"vendor": v, "product": p}
            out["names_from"] = out["names_from"] or "usb.ids"
    if online:
        odb = opendevicedb(vid, pid, fetch)
        out["opendevicedb"] = odb
        if odb["records"] and out["status"] == "unknown":
            out["status"] = "listed in OpenDeviceDB"
    return out


def from_capture(capture: str | Path) -> list[tuple[int, int, int]]:
    """(device address, vid, pid) for every device whose descriptor is in the capture."""
    from .pcap import find_ids, read_transfers
    return [(d, v, p) for d, (v, p) in sorted(find_ids(read_transfers(capture)).items())]


def render(info: dict) -> str:
    v, p = info["vendor"], info["product"]
    name = f"{p} ({v})" if p and v else p or v or "unknown device"
    L = [f"{info['id']}  {name}", f"  protocol: {info['status']}"]
    for p in info["projects"]:
        L.append(f"  - {p['project']}: {p['url']}" + (f" ({p['note']})" if p.get("note") else ""))
    if info.get("limits"):
        L.append(f"  limits: {info['limits']}")
    if info["status"] == "unknown" and info["same_vendor"]:
        L.append(f"  other devices from this vendor are handled by: {', '.join(info['same_vendor'])}")
    odb = info.get("opendevicedb")
    if odb is not None:
        if odb.get("error"):
            L.append(f"  OpenDeviceDB: not reachable ({odb['error']}); offline answer above")
        elif not odb["records"]:
            L.append("  OpenDeviceDB: no record for this ID")
        for r in odb["records"]:
            L.append(f"  OpenDeviceDB: {r['vendor']} {r['model']}, {r['status']} ({', '.join(r['sources'])}): {r['url']}")
            L += [f"    - {p['project']}: {p['url']}" for p in r["projects"]]
    if info["status"] == "unknown" and odb is None:
        L.append("  nothing known offline; try --online (OpenDeviceDB) or capture it and find out")
    if info["projects"] or (odb and odb["records"]):
        L.append(f"  note: {info['note']}")
    return "\n".join(L)
