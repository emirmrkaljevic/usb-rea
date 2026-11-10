"""Look up a USB VID:PID before capturing: has someone already documented this device's protocol?

Offline first. The answer comes from a table of devices whose protocol an open-source project
already implements (liquidctl, rivalcfg, turing-smart-screen-python, linux-thermalright-lcd-control,
a curated OpenRGB set, and usb-rea's own case studies), plus vendor and product names from a local
usb.ids file when one is installed (usbutils/hwdata ship it). `online=True` also asks
OpenDeviceDB (https://opendevicedb.org, its read-only static API); without a network that part just
reports the error and the offline answer stays as it is.

A matching USB ID is a hint, not proof: vendors reuse IDs across revisions and generic chips
(a WCH serial bridge, for example) carry the same ID in unrelated products. Each table entry cites
the public source file it was taken from.
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
OPENRGB = "https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/"
DOCS = "https://github.com/emirmrkaljevic/usb-rea/blob/main/docs/"

VENDORS = {
    0x0416: "Winbond Electronics Corp.",
    0x048D: "ITE Tech. Inc.",
    0x0B05: "ASUSTek Computer, Inc.",
    0x0C70: "Aqua Computer GmbH",
    0x0CF2: "Lian Li",
    0x0DB0: "Micro Star International",
    0x1038: "SteelSeries ApS",
    0x1A86: "QinHeng Electronics",
    0x1B1C: "Corsair",
    0x1D6B: "Linux Foundation",
    0x1E71: "NZXT",
    0x2433: "Asetek",
    0x2516: "Cooler Master",
    0x264A: "Thermaltake",
    0x0525: "Netchip Technology, Inc.",
}


def _p(name, url, note=""):
    return {"project": name, "url": url, "note": note}


def _liq(driver, note=""):
    return _p("liquidctl", LIQUIDCTL + driver, note)


def _riv(module, note="DPI, polling rate, lighting"):
    return _p("rivalcfg", RIVALCFG + module, note)


def _tur(note=""):
    return _p("turing-smart-screen-python", TURING, note)


def _rgb(controller, note="RGB lighting"):
    return _p("OpenRGB", OPENRGB + controller, note)


def _dev(vid, pid, name, projects, limits=None):
    entry = {"name": name, "projects": list(projects)}
    if limits:
        entry["limits"] = limits
    KNOWN[(vid, pid)] = entry


# (vid, pid) -> name, projects that implement or document the protocol, and limits worth knowing
# IDs below are copied from the cited public sources (not from private captures).
KNOWN: dict[tuple[int, int], dict] = {}


# liquidctl kraken2.py: https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/kraken2.py
_dev(0x1E71, 0x170E, "NZXT Kraken X (X42, X52, X62 or X72)", [
    _liq("kraken2.py", "fan/pump duty, lighting, status"),
    _rgb("NZXTKrakenController/NZXTKrakenControllerDetect.cpp"),
    _p("usb-rea validation", DOCS + "VALIDATION.md", "fan duty command recovered byte for byte")])
_dev(0x1E71, 0x1715, "NZXT Kraken M22", [_liq("kraken2.py"), _rgb("NZXTKrakenController/NZXTKrakenControllerDetect.cpp")])

# liquidctl kraken3.py: https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/kraken3.py
_dev(0x1E71, 0x2007, "NZXT Kraken X (X53, X63 or X73)", [_liq("kraken3.py")])
_dev(0x1E71, 0x2014, "NZXT Kraken X (X53, X63 or X73)", [_liq("kraken3.py")])
_dev(0x1E71, 0x3008, "NZXT Kraken Z (Z53, Z63 or Z73)", [_liq("kraken3.py", "includes the 320x320 LCD")])
_dev(0x1E71, 0x300C, "NZXT Kraken 2023 Elite", [_liq("kraken3.py")],
     limits="liquidctl marks this match as broken")
_dev(0x1E71, 0x300E, "NZXT Kraken 2023", [_liq("kraken3.py")])
_dev(0x1E71, 0x3012, "NZXT Kraken 2024 Elite RGB", [_liq("kraken3.py"),
     _rgb("NZXTHue2Controller/NZXTHue2ControllerDetect.cpp")])
_dev(0x1E71, 0x3014, "NZXT Kraken 2024 Plus", [_liq("kraken3.py")])

# liquidctl hydro_platinum.py: https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py
HP = [_liq("hydro_platinum.py"), _rgb("CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp")]
_dev(0x1B1C, 0x0C18, "Corsair Hydro H100i Platinum", HP + [
    _p("usb-rea case study", DOCS + "case-study-hydro-platinum.md", "CRC8 and sequence counter recovered")])
_dev(0x1B1C, 0x0C19, "Corsair Hydro H100i Platinum SE", HP)
_dev(0x1B1C, 0x0C17, "Corsair Hydro H115i Platinum", HP)
_dev(0x1B1C, 0x0C29, "Corsair Hydro H60i Pro XT", HP)
_dev(0x1B1C, 0x0C20, "Corsair Hydro H100i Pro XT", HP)
_dev(0x1B1C, 0x0C21, "Corsair Hydro H115i Pro XT", HP)
_dev(0x1B1C, 0x0C22, "Corsair Hydro H150i Pro XT", HP)
_dev(0x1B1C, 0x0C35, "Corsair iCUE H100i Elite RGB", HP)
_dev(0x1B1C, 0x0C36, "Corsair iCUE H115i Elite RGB", HP)
_dev(0x1B1C, 0x0C37, "Corsair iCUE H150i Elite RGB", HP)
_dev(0x1B1C, 0x0C40, "Corsair iCUE H100i Elite RGB (White)", HP)
_dev(0x1B1C, 0x0C41, "Corsair iCUE H150i Elite RGB (White)", HP)
# OpenRGB lists this Platinum-family PID; liquidctl hydro_platinum.py does not (as of the copy used here)
_dev(0x1B1C, 0x0C2D, "Corsair Hydro H100i Pro XT V2",
     [_rgb("CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp")])

# liquidctl asetek.py / asetek_pro.py / coolit.py
_dev(0x2433, 0xB200, "Asetek 690LC (EVGA CLC or NZXT Kraken X, depending on the driver)",
     [_liq("asetek.py")],
     limits="the same ID is used by more than one Asetek 690LC rebrand; liquidctl has separate drivers")
_dev(0x1B1C, 0x0C02, "Corsair Hydro H80i GT", [_liq("asetek.py")])
_dev(0x1B1C, 0x0C03, "Corsair Hydro H100i GTX", [_liq("asetek.py")])
_dev(0x1B1C, 0x0C07, "Corsair Hydro H110i GTX", [_liq("asetek.py")])
_dev(0x1B1C, 0x0C08, "Corsair Hydro H80i v2", [_liq("asetek.py")])
_dev(0x1B1C, 0x0C09, "Corsair Hydro H100i v2", [_liq("asetek.py")])
_dev(0x1B1C, 0x0C0A, "Corsair Hydro H115i", [_liq("asetek.py")])
_dev(0x1B1C, 0x0C12, "Corsair Hydro H150i Pro", [_liq("asetek_pro.py")])
_dev(0x1B1C, 0x0C13, "Corsair Hydro H115i Pro", [_liq("asetek_pro.py")])
_dev(0x1B1C, 0x0C15, "Corsair Hydro H100i Pro", [_liq("asetek_pro.py")])
_dev(0x1B1C, 0x0C04, "Corsair H110i GT", [_liq("coolit.py")])

# liquidctl asus_ryuo.py, asus_ryujin.py, aura_led.py
_dev(0x0B05, 0x1887, "ASUS Ryuo I 240", [_liq("asus_ryuo.py")])
_dev(0x0B05, 0x1988, "ASUS Ryujin II 360", [_liq("asus_ryujin.py")])
_dev(0x0B05, 0x1BCB, "ASUS Ryujin III Extreme", [_liq("asus_ryujin.py")])
_dev(0x0B05, 0x1AA2, "ASUS Ryujin III 360", [_liq("asus_ryujin.py")])
_dev(0x0B05, 0x1ADE, "ASUS Ryujin III EVA", [_liq("asus_ryujin.py")])
_dev(0x0B05, 0x1ADA, "ASUS Ryujin III White", [_liq("asus_ryujin.py")])
_dev(0x0B05, 0x19AF, "ASUS Aura LED Controller", [_liq("aura_led.py")])
_dev(0x0B05, 0x1939, "ASUS Aura LED Controller", [_liq("aura_led.py")],
     limits="liquidctl notes this ID is not fully supported yet")
_dev(0x0B05, 0x18F3, "ASUS Aura LED Controller", [_liq("aura_led.py")],
     limits="liquidctl notes this ID is not fully supported yet")
_dev(0x0B05, 0x1C7B, "ASUS TUF Gaming LC III LCD", [
    _p("usb-rea case study", DOCS + "case-study-asus-tuf-lc3.md",
       "brightness command and JPEG stream from one real capture; not a full driver")])

# liquidctl commander_pro.py / commander_core.py
LN = [_liq("commander_pro.py"), _rgb("CorsairLightingNodeController/CorsairLightingNodeControllerDetect.cpp")]
_dev(0x1B1C, 0x0C10, "Corsair Commander Pro", LN)
_dev(0x1B1C, 0x0C0B, "Corsair Lighting Node Pro", LN)
_dev(0x1B1C, 0x0C1A, "Corsair Lighting Node Core", LN)
_dev(0x1B1C, 0x1D00, "Corsair Obsidian 1000D", LN)
_dev(0x1B1C, 0x0C1C, "Corsair Commander Core", [_liq("commander_core.py")],
     limits="liquidctl marks this match as broken")
_dev(0x1B1C, 0x0C2A, "Corsair Commander Core XT", [_liq("commander_core.py")],
     limits="liquidctl marks this match as broken")
_dev(0x1B1C, 0x0C32, "Corsair Commander ST", [_liq("commander_core.py")],
     limits="liquidctl marks this match as broken")
# OpenRGB Lighting Node family IDs that commander_pro.py does not list
_dev(0x1B1C, 0x0C1E, "Corsair LS100",
     [_rgb("CorsairLightingNodeController/CorsairLightingNodeControllerDetect.cpp")])
_dev(0x1B1C, 0x1D04, "Corsair SPEC OMEGA RGB",
     [_rgb("CorsairLightingNodeController/CorsairLightingNodeControllerDetect.cpp")])
_dev(0x1B1C, 0x0C23, "Corsair LT100",
     [_rgb("CorsairLightingNodeController/CorsairLightingNodeControllerDetect.cpp")])

# liquidctl smart_device.py / control_hub.py
HUE = [_liq("smart_device.py"), _rgb("NZXTHue2Controller/NZXTHue2ControllerDetect.cpp")]
_dev(0x1E71, 0x1714, "NZXT Smart Device (V1)", [_liq("smart_device.py")])
_dev(0x1E71, 0x1711, "NZXT Grid+ V3", [_liq("smart_device.py")])
_dev(0x1E71, 0x2006, "NZXT Smart Device V2", HUE)
_dev(0x1E71, 0x200D, "NZXT Smart Device V2", HUE)
_dev(0x1E71, 0x200F, "NZXT Smart Device V2", HUE)
_dev(0x1E71, 0x2001, "NZXT HUE 2", HUE)
_dev(0x1E71, 0x2002, "NZXT HUE 2 Ambient", HUE)
_dev(0x1E71, 0x2009, "NZXT RGB & Fan Controller", HUE)
_dev(0x1E71, 0x200E, "NZXT RGB & Fan Controller", HUE)
_dev(0x1E71, 0x2010, "NZXT RGB & Fan Controller", HUE)
_dev(0x1E71, 0x2011, "NZXT RGB & Fan Controller (3+6 channels)", HUE)
_dev(0x1E71, 0x2019, "NZXT RGB & Fan Controller (3+6 channels)", HUE)
_dev(0x1E71, 0x201F, "NZXT RGB & Fan Controller (3+6 channels)", HUE)
_dev(0x1E71, 0x2020, "NZXT RGB & Fan Controller (3+6 channels)", HUE)
_dev(0x1E71, 0x2015, "NZXT H1 V2", [_liq("smart_device.py")])
_dev(0x1E71, 0x2012, "NZXT 2023 RGB Controller", HUE)
_dev(0x1E71, 0x2021, "NZXT 2023 RGB Controller", HUE)
_dev(0x1E71, 0x2022, "NZXT Control Hub", [_liq("control_hub.py"),
     _rgb("NZXTHue2Controller/NZXTHue2ControllerDetect.cpp")])
# OpenRGB Hue 2 family IDs that smart_device.py does not list
_dev(0x1E71, 0x2005, "NZXT motherboard RGB device",
     [_rgb("NZXTHue2Controller/NZXTHue2ControllerDetect.cpp")])
_dev(0x1E71, 0x200B, "NZXT motherboard RGB device",
     [_rgb("NZXTHue2Controller/NZXTHue2ControllerDetect.cpp")])
_dev(0x1E71, 0x201B, "NZXT RGB & Fan Controller",
     [_rgb("NZXTHue2Controller/NZXTHue2ControllerDetect.cpp")])

# liquidctl corsair_hid_psu.py, lianli_uni.py, msi.py, ga2_lcd.py, aquacomputer.py, rgb_fusion2.py, nzxt_epsu.py
_dev(0x1B1C, 0x1C05, "Corsair HX750i", [_liq("corsair_hid_psu.py")])
_dev(0x1B1C, 0x1C06, "Corsair HX850i", [_liq("corsair_hid_psu.py")])
_dev(0x1B1C, 0x1C07, "Corsair HX1000i", [_liq("corsair_hid_psu.py")])
_dev(0x1B1C, 0x1C08, "Corsair HX1200i", [_liq("corsair_hid_psu.py")])
_dev(0x1B1C, 0x1C23, "Corsair HX1200i ATX 3.1", [_liq("corsair_hid_psu.py")])
_dev(0x1B1C, 0x1C27, "Corsair HX1200i ATX 3.1 #2", [_liq("corsair_hid_psu.py")])
_dev(0x1B1C, 0x1C0A, "Corsair RM650i", [_liq("corsair_hid_psu.py")])
_dev(0x1B1C, 0x1C0B, "Corsair RM750i", [_liq("corsair_hid_psu.py")])
_dev(0x1B1C, 0x1C0C, "Corsair RM850i", [_liq("corsair_hid_psu.py")])
_dev(0x1B1C, 0x1C0D, "Corsair RM1000i", [_liq("corsair_hid_psu.py")])
_dev(0x1B1C, 0x1C1E, "Corsair HX1000i (2022)", [_liq("corsair_hid_psu.py")])
_dev(0x1B1C, 0x1C1F, "Corsair HX1500i", [_liq("corsair_hid_psu.py")])
_dev(0x0CF2, 0x7750, "Lian Li Uni SL", [_liq("lianli_uni.py")])
_dev(0x0CF2, 0xA100, "Lian Li Uni SL", [_liq("lianli_uni.py")])
_dev(0x0CF2, 0xA101, "Lian Li Uni AL", [_liq("lianli_uni.py")])
_dev(0x0CF2, 0xA102, "Lian Li Uni SL-Infinity", [_liq("lianli_uni.py")])
_dev(0x0CF2, 0xA103, "Lian Li Uni SL V2", [_liq("lianli_uni.py")])
_dev(0x0CF2, 0xA104, "Lian Li Uni AL V2", [_liq("lianli_uni.py")])
_dev(0x0CF2, 0xA105, "Lian Li Uni SL V2", [_liq("lianli_uni.py")])
_dev(0x0DB0, 0xB130, "MSI MPG Coreliquid K360", [_liq("msi.py")])
_dev(0x0416, 0x7395, "Lian Li GA II LCD", [_liq("ga2_lcd.py")])
_dev(0x0C70, 0xF00E, "Aquacomputer D5 Next", [_liq("aquacomputer.py")])
_dev(0x0C70, 0xF00A, "Aquacomputer Farbwerk", [_liq("aquacomputer.py")])
_dev(0x0C70, 0xF010, "Aquacomputer Farbwerk 360", [_liq("aquacomputer.py")])
_dev(0x0C70, 0xF011, "Aquacomputer Octo", [_liq("aquacomputer.py")])
_dev(0x0C70, 0xF00D, "Aquacomputer Quadro", [_liq("aquacomputer.py")])
FUSION = [_liq("rgb_fusion2.py"), _rgb("GigabyteRGBFusion2USBController/GigabyteRGBFusion2USBControllerDetect.cpp")]
_dev(0x048D, 0x5702, "Gigabyte RGB Fusion 2.0 5702 Controller", FUSION)
_dev(0x048D, 0x8297, "Gigabyte RGB Fusion 2.0 8297 Controller", FUSION)
_dev(0x048D, 0x8950, "Gigabyte RGB Fusion 2 USB",
     [_rgb("GigabyteRGBFusion2USBController/GigabyteRGBFusion2USBControllerDetect.cpp")])
_dev(0x048D, 0x5711, "Gigabyte RGB Fusion 2 USB",
     [_rgb("GigabyteRGBFusion2USBController/GigabyteRGBFusion2USBControllerDetect.cpp")])
_dev(0x0414, 0xA100, "Gigabyte RGB Fusion 2 USB",
     [_rgb("GigabyteRGBFusion2USBController/GigabyteRGBFusion2USBControllerDetect.cpp")])
_dev(0x7793, 0x5911, "NZXT E500", [_liq("nzxt_epsu.py")])
_dev(0x7793, 0x5912, "NZXT E650", [_liq("nzxt_epsu.py")])
_dev(0x7793, 0x2500, "NZXT E850", [_liq("nzxt_epsu.py")])

# rivalcfg device modules: https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/
_dev(0x1038, 0x1836, "SteelSeries Aerox 3", [_riv("aerox3.py")])
_dev(0x1038, 0x183A, "SteelSeries Aerox 3 Wireless (wired mode)", [_riv("aerox3_wireless_wired.py")])
_dev(0x1038, 0x187A, "SteelSeries Aerox 3 Wireless CS2 Dragon Lore Edition (wired mode)", [_riv("aerox3_wireless_wired.py")])
_dev(0x1038, 0x1838, "SteelSeries Aerox 3 Wireless (2.4 GHz wireless mode)", [_riv("aerox3_wireless_wireless.py")])
_dev(0x1038, 0x1878, "SteelSeries Aerox 3 Wireless CS2 Dragon Lore Edition (2.4 GHz wireless mode)", [_riv("aerox3_wireless_wireless.py")])
_dev(0x1038, 0x1850, "SteelSeries Aerox 5", [_riv("aerox5.py")])
_dev(0x1038, 0x1854, "SteelSeries Aerox 5 Wireless (wired mode)", [_riv("aerox5_wireless_wired.py")])
_dev(0x1038, 0x185E, "SteelSeries Aerox 5 Wireless Destiny 2 Edition (wired mode)", [_riv("aerox5_wireless_wired.py")])
_dev(0x1038, 0x1862, "SteelSeries Aerox 5 Wireless Diablo IV Edition (wired mode)", [_riv("aerox5_wireless_wired.py")])
_dev(0x1038, 0x1852, "SteelSeries Aerox 5 Wireless (2.4 GHz wireless mode)", [_riv("aerox5_wireless_wireless.py")])
_dev(0x1038, 0x185C, "SteelSeries Aerox 5 Wireless Destiny 2 Edition (2.4 GHz wireless mode)", [_riv("aerox5_wireless_wireless.py")])
_dev(0x1038, 0x1860, "SteelSeries Aerox 5 Wireless Diablo IV Edition (2.4 GHz wireless mode)", [_riv("aerox5_wireless_wireless.py")])
_dev(0x1038, 0x185A, "SteelSeries Aerox 9 Wireless (wired mode)", [_riv("aerox9_wireless_wired.py")])
_dev(0x1038, 0x1876, "SteelSeries Aerox 9 Wireless WOW Edition (wired mode)", [_riv("aerox9_wireless_wired.py")])
_dev(0x1038, 0x1858, "SteelSeries Aerox 9 Wireless (2.4 GHz wireless mode)", [_riv("aerox9_wireless_wireless.py")])
_dev(0x1038, 0x1874, "SteelSeries Aerox 9 Wireless WOW Edition (2.4 GHz wireless mode)", [_riv("aerox9_wireless_wireless.py")])
_dev(0x1038, 0x137A, "SteelSeries Kana v2", [_riv("kanav2.py")])
_dev(0x1038, 0x1366, "SteelSeries Kinzu v2", [_riv("kinzuv2.py")])
_dev(0x1038, 0x1378, "SteelSeries Kinzu v2", [_riv("kinzuv2.py")])
_dev(0x1038, 0x182E, "SteelSeries Prime", [_riv("prime.py")])
_dev(0x1038, 0x182A, "SteelSeries Prime Rainbow 6 Siege Black Ice Edition", [_riv("prime.py")])
_dev(0x1038, 0x1856, "SteelSeries Prime CS:GO Neo Noir Edition", [_riv("prime.py")])
_dev(0x1038, 0x184D, "SteelSeries Prime Mini", [_riv("prime_mini.py")])
_dev(0x1038, 0x182C, "SteelSeries Prime+", [_riv("prime_plus.py")])
_dev(0x1038, 0x1842, "SteelSeries Prime Wireless (wired mode)", [_riv("prime_wireless_wired.py")])
_dev(0x1038, 0x184A, "SteelSeries Prime Mini Wireless (wired mode)", [_riv("prime_wireless_wired.py")])
_dev(0x1038, 0x1840, "SteelSeries Prime Wireless (2.4 GHz wireless mode)", [_riv("prime_wireless_wireless.py")])
_dev(0x1038, 0x1848, "SteelSeries Prime Mini Wireless (2.4 GHz wireless mode)", [_riv("prime_wireless_wireless.py")])
_dev(0x1038, 0x1702, "SteelSeries Rival 100", [
    _riv("rival100.py"),
    _p("usb-rea validation", DOCS + "VALIDATION.md", "DPI/polling lookup tables recovered")])
_dev(0x1038, 0x170A, "SteelSeries Rival 100 (Dell China)", [_riv("rival100.py")])
_dev(0x1038, 0x170B, "SteelSeries Rival 100 Dota 2 Edition (retail)", [_riv("rival100.py")])
_dev(0x1038, 0x170C, "SteelSeries Rival 100 Dota 2 Edition (Lenovo)", [_riv("rival100.py")])
_dev(0x1038, 0x1814, "SteelSeries Rival 105", [_riv("rival100.py")])
_dev(0x1038, 0x1729, "SteelSeries Rival 110", [_riv("rival110.py")])
_dev(0x1038, 0x1816, "SteelSeries Rival 106", [_riv("rival110.py")])
_dev(0x1038, 0x1824, "SteelSeries Rival 3", [_riv("rival3.py")])
_dev(0x1038, 0x184C, "SteelSeries Rival 3 (firmware v0.37.0.0)", [_riv("rival3.py")])
_dev(0x1038, 0x1384, "SteelSeries Rival", [_riv("rival300.py")])
_dev(0x1038, 0x1392, "SteelSeries Rival Dota 2 Edition", [_riv("rival300.py")])
_dev(0x1038, 0x1710, "SteelSeries Rival 300", [_riv("rival300.py")])
_dev(0x1038, 0x1712, "SteelSeries Rival 300 Fallout 4 Edition", [_riv("rival300.py")])
_dev(0x1038, 0x171C, "SteelSeries Rival 300 Evil Geniuses Edition", [_riv("rival300.py")])
_dev(0x1038, 0x1394, "SteelSeries Rival 300 CS:GO Fade Edition", [_riv("rival300.py")])
_dev(0x1038, 0x171A, "SteelSeries Rival 300 CS:GO Hyper Beast Edition", [_riv("rival300.py")])
_dev(0x1038, 0x1716, "SteelSeries Rival 300 CS:GO Fade Edition (stm32)", [_riv("rival300.py")])
_dev(0x1038, 0x1714, "SteelSeries Rival 300 Acer Predator Edition", [_riv("rival300.py")])
_dev(0x1038, 0x1718, "SteelSeries Rival 300 HP OMEN Edition", [_riv("rival300.py")])
_dev(0x1038, 0x1810, "SteelSeries Rival 300S", [_riv("rival300s.py")])
_dev(0x1038, 0x1720, "SteelSeries Rival 310", [_riv("rival310.py")])
_dev(0x1038, 0x171E, "SteelSeries Rival 310 CS:GO Howl Edition", [_riv("rival310.py")])
_dev(0x1038, 0x1736, "SteelSeries Rival 310 PUBG Edition", [_riv("rival310.py")])
_dev(0x1038, 0x1870, "SteelSeries Rival 3 Gen 2", [_riv("rival3_gen2.py")])
_dev(0x1038, 0x1830, "SteelSeries Rival 3 Wireless (2.4 GHz mode)", [_riv("rival3_wireless.py")])
_dev(0x1038, 0x1872, "SteelSeries Rival 3 Wireless Gen 2 (2.4 GHz mode)", [_riv("rival3_wireless_gen2.py")])
_dev(0x1038, 0x183C, "SteelSeries Rival 5", [_riv("rival5.py")])
_dev(0x1038, 0x183E, "SteelSeries Rival 5 Destiny Edition", [_riv("rival5.py")])
_dev(0x1038, 0x170E, "SteelSeries Rival 500", [_riv("rival500.py")])
_dev(0x1038, 0x1724, "SteelSeries Rival 600", [_riv("rival600.py")])
_dev(0x1038, 0x172E, "SteelSeries Rival 600 Dota 2 Edition", [_riv("rival600.py")])
_dev(0x1038, 0x172B, "SteelSeries Rival 650 Wireless (wired mode)", [_riv("rival650.py")])
_dev(0x1038, 0x1726, "SteelSeries Rival 650 Wireless (2.4 GHz wireless mode)", [_riv("rival650.py")])
_dev(0x1038, 0x1700, "SteelSeries Rival 700", [_riv("rival700.py")])
_dev(0x1038, 0x1730, "SteelSeries Rival 710", [_riv("rival700.py")])
_dev(0x1038, 0x1706, "SteelSeries Rival 95", [_riv("rival95.py")])
_dev(0x1038, 0x1707, "SteelSeries Rival 95 MSI Edition", [_riv("rival95.py")])
_dev(0x1038, 0x1704, "SteelSeries Rival 95 PC Bang", [_riv("rival95.py")])
_dev(0x1038, 0x1708, "SteelSeries Rival 100 PC Bang", [_riv("rival95.py")])
_dev(0x1038, 0x1722, "SteelSeries Sensei 310", [_riv("sensei310.py")])
_dev(0x1038, 0x1369, "SteelSeries Sensei [RAW]", [_riv("sensei_raw.py")])
_dev(0x1038, 0x1362, "SteelSeries Sensei [RAW] Diablo III Edition", [_riv("sensei_raw.py")])
_dev(0x1038, 0x136D, "SteelSeries Sensei [RAW] Guild Wars 2 Edition", [_riv("sensei_raw.py")])
_dev(0x1038, 0x136F, "SteelSeries Sensei [RAW] CoD Black Ops II Edition", [_riv("sensei_raw.py")])
_dev(0x1038, 0x1380, "SteelSeries Sensei [RAW] World of Tanks Edition", [_riv("sensei_raw.py")])
_dev(0x1038, 0x1390, "SteelSeries Sensei [RAW] Heroes of the Storm Edition", [_riv("sensei_raw.py")])
_dev(0x1038, 0x1832, "SteelSeries Sensei TEN", [_riv("sensei_ten.py")])
_dev(0x1038, 0x1834, "SteelSeries Sensei TEN CS:GO Neon Rider Edition", [_riv("sensei_ten.py")])

# turing-smart-screen-python: library/lcd/lcd_comm_rev_*.py, lcd_comm_turing_usb.py, lcd_comm_weact_*.py
_dev(0x1A86, 0x5722, "Turing Smart Screen 3.5\" (rev A) / XuanFang (rev B)", [_tur("serial protocol for revisions A and B")],
     limits="generic WCH serial bridge ID; the project tells revisions apart by the USB serial "
             "number (USB35INCHIPSV2 is rev A, 2017-2-25 is rev B), and unrelated devices use this ID too")
_dev(0x1A86, 0xCA21, "Turing / UsbPCMonitor 7-inch class screen (rev C, sleeping)", [_tur("rev C serial protocol")],
     limits="the project also looks at serial numbers USB7INCH, CT21INCH and CT88INCH")
_dev(0x0525, 0xA4A7, "Turing / UsbPCMonitor screen (rev C, awake)", [_tur("rev C serial protocol")],
     limits="this is a common Linux USB gadget ID (Netchip); unrelated gadgets use it too")
_dev(0x1D6B, 0x0121, "Turing / UsbPCMonitor screen (rev C, awake)", [_tur("rev C serial protocol")],
     limits="Linux Foundation gadget ID; unrelated USB gadgets use it too")
_dev(0x1D6B, 0x0106, "Turing / UsbPCMonitor screen (rev C, awake)", [_tur("rev C serial protocol")],
     limits="Linux Foundation gadget ID; unrelated USB gadgets use it too")
_dev(0x454D, 0x4E41, "Turing-compatible LCD (rev D)", [_tur("rev D serial protocol")])
_dev(0x1A86, 0xFE0C, "WeAct Studio USB display (rev A or B)", [_tur("WeAct A/B serial protocol")],
     limits="the project tells revisions apart by the USB serial number (AB... is WeAct A, AD... is WeAct B)")

# turing lcd_comm_turing_usb.py PRODUCT_ID map (WinUSB, not a serial port)
_dev(0x1CBE, 0x0028, "Turing 2.8-inch round (USB)", [_tur("native USB protocol, not serial")])
_dev(0x1CBE, 0x0046, "Turing 4.6-inch (USB)", [_tur("native USB protocol, not serial")])
_dev(0x1CBE, 0x0050, "Turing 5.2-inch (USB)", [_tur("native USB protocol, not serial")])
_dev(0x1CBE, 0x0080, "Turing 8.0-inch (USB)", [_tur("native USB protocol, not serial")])
_dev(0x1CBE, 0x0088, "Turing 8.8-inch (USB)", [_tur("native USB protocol, not serial")])
_dev(0x1CBE, 0x0092, "Turing 9.2-inch (USB)", [_tur("native USB protocol, not serial")])
_dev(0x1CBE, 0x0123, "Turing 12.3-inch (USB)", [_tur("native USB protocol, not serial")])

# linux-thermalright-lcd-control: https://github.com/rejeb/linux-thermalright-lcd-control
_dev(0x0416, 0x5302, "Thermalright LCD (ChiZhu, 320x240, HID)", [_p("linux-thermalright-lcd-control", THERMALRIGHT)],
     limits="Winbond/Nuvoton generic ID used by other products as well")
_dev(0x87AD, 0x70DB, "Thermalright LCD (ChiZhu, 320/480/640 variants)", [_p("linux-thermalright-lcd-control", THERMALRIGHT)])
_dev(0x0416, 0x5408, "Thermalright LCD (LY)", [_p("linux-thermalright-lcd-control", THERMALRIGHT)])
_dev(0x0416, 0x5409, "Thermalright LCD (LY)", [_p("linux-thermalright-lcd-control", THERMALRIGHT)])

# OpenRGB CoolerMasterControllerDetect.cpp (ARGB/RGB hubs only, not every keyboard/mouse)
CM = "CoolerMasterController/CoolerMasterControllerDetect.cpp"
_dev(0x2516, 0x1011, "Cooler Master ARGB", [_rgb(CM)])
_dev(0x2516, 0x0173, "Cooler Master ARGB Gen 2 A1", [_rgb(CM)])
_dev(0x2516, 0x01C9, "Cooler Master ARGB Gen 2 A1 V2", [_rgb(CM)])
_dev(0x2516, 0x01CB, "Cooler Master ARGB Gen 2 A1 Mini", [_rgb(CM)])
_dev(0x2516, 0x1000, "Cooler Master Small ARGB", [_rgb(CM)])
_dev(0x2516, 0x004F, "Cooler Master RGB", [_rgb(CM)])

# OpenRGB ThermaltakeRiingControllerDetect.cpp
TT = "ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp"
_dev(0x264A, 0x1FA5, "Thermaltake Riing (PID 0x1FA5)", [_rgb(TT)])
_dev(0x264A, 0x1FA6, "Thermaltake Riing (PID 0x1FA6)", [_rgb(TT)])
_dev(0x264A, 0x1FA7, "Thermaltake Riing (PID 0x1FA7)", [_rgb(TT)])
_dev(0x264A, 0x1FA8, "Thermaltake Riing (PID 0x1FA8)", [_rgb(TT)])
_dev(0x264A, 0x1FA9, "Thermaltake Riing (PID 0x1FA9)", [_rgb(TT)])
_dev(0x264A, 0x1FAA, "Thermaltake Riing (PID 0x1FAA)", [_rgb(TT)])
_dev(0x264A, 0x1FAB, "Thermaltake Riing (PID 0x1FAB)", [_rgb(TT)])
_dev(0x264A, 0x1FAC, "Thermaltake Riing (PID 0x1FAC)", [_rgb(TT)])
_dev(0x264A, 0x1FAD, "Thermaltake Riing (PID 0x1FAD)", [_rgb(TT)])
_dev(0x264A, 0x1FAE, "Thermaltake Riing (PID 0x1FAE)", [_rgb(TT)])
_dev(0x264A, 0x1FAF, "Thermaltake Riing (PID 0x1FAF)", [_rgb(TT)])
_dev(0x264A, 0x1FB0, "Thermaltake Riing (PID 0x1FB0)", [_rgb(TT)])
_dev(0x264A, 0x1FB1, "Thermaltake Riing (PID 0x1FB1)", [_rgb(TT)])
_dev(0x264A, 0x1FB2, "Thermaltake Riing (PID 0x1FB2)", [_rgb(TT)])
_dev(0x264A, 0x1FB3, "Thermaltake Riing (PID 0x1FB3)", [_rgb(TT)])
_dev(0x264A, 0x1FB4, "Thermaltake Riing (PID 0x1FB4)", [_rgb(TT)])
_dev(0x264A, 0x1FB5, "Thermaltake Riing (PID 0x1FB5)", [_rgb(TT)])
_dev(0x264A, 0x2260, "Thermaltake Riing Quad (PID 0x2260)", [_rgb(TT)])
_dev(0x264A, 0x2261, "Thermaltake Riing Quad (PID 0x2261)", [_rgb(TT)])
_dev(0x264A, 0x2262, "Thermaltake Riing Quad (PID 0x2262)", [_rgb(TT)])
_dev(0x264A, 0x2263, "Thermaltake Riing Quad (PID 0x2263)", [_rgb(TT)])
_dev(0x264A, 0x2264, "Thermaltake Riing Quad (PID 0x2264)", [_rgb(TT)])
_dev(0x264A, 0x2265, "Thermaltake Riing Quad (PID 0x2265)", [_rgb(TT)])
_dev(0x264A, 0x2266, "Thermaltake Riing Quad (PID 0x2266)", [_rgb(TT)])
_dev(0x264A, 0x2267, "Thermaltake Riing Quad (PID 0x2267)", [_rgb(TT)])
_dev(0x264A, 0x2268, "Thermaltake Riing Quad (PID 0x2268)", [_rgb(TT)])
_dev(0x264A, 0x2269, "Thermaltake Riing Quad (PID 0x2269)", [_rgb(TT)])
_dev(0x264A, 0x226A, "Thermaltake Riing Quad (PID 0x226A)", [_rgb(TT)])
_dev(0x264A, 0x226B, "Thermaltake Riing Quad (PID 0x226B)", [_rgb(TT)])
_dev(0x264A, 0x226C, "Thermaltake Riing Quad (PID 0x226C)", [_rgb(TT)])
_dev(0x264A, 0x226D, "Thermaltake Riing Quad (PID 0x226D)", [_rgb(TT)])
_dev(0x264A, 0x226E, "Thermaltake Riing Quad (PID 0x226E)", [_rgb(TT)])
_dev(0x264A, 0x226F, "Thermaltake Riing Quad (PID 0x226F)", [_rgb(TT)])
_dev(0x264A, 0x2270, "Thermaltake Riing Quad (PID 0x2270)", [_rgb(TT)])
_dev(0x264A, 0x232B, "Thermaltake Riing Quad (PID 0x232B)", [_rgb(TT)])
_dev(0x264A, 0x2135, "Thermaltake Riing Trio (PID 0x2135)", [_rgb(TT)])
_dev(0x264A, 0x2136, "Thermaltake Riing Trio (PID 0x2136)", [_rgb(TT)])
_dev(0x264A, 0x2137, "Thermaltake Riing Trio (PID 0x2137)", [_rgb(TT)])
_dev(0x264A, 0x2138, "Thermaltake Riing Trio (PID 0x2138)", [_rgb(TT)])
_dev(0x264A, 0x2139, "Thermaltake Riing Trio (PID 0x2139)", [_rgb(TT)])
_dev(0x264A, 0x213A, "Thermaltake Riing Trio (PID 0x213A)", [_rgb(TT)])
_dev(0x264A, 0x213B, "Thermaltake Riing Trio (PID 0x213B)", [_rgb(TT)])
_dev(0x264A, 0x213C, "Thermaltake Riing Trio (PID 0x213C)", [_rgb(TT)])
_dev(0x264A, 0x213D, "Thermaltake Riing Trio (PID 0x213D)", [_rgb(TT)])
_dev(0x264A, 0x213E, "Thermaltake Riing Trio (PID 0x213E)", [_rgb(TT)])
_dev(0x264A, 0x213F, "Thermaltake Riing Trio (PID 0x213F)", [_rgb(TT)])
_dev(0x264A, 0x2141, "Thermaltake Riing Trio (PID 0x2141)", [_rgb(TT)])
_dev(0x264A, 0x2142, "Thermaltake Riing Trio (PID 0x2142)", [_rgb(TT)])
_dev(0x264A, 0x2143, "Thermaltake Riing Trio (PID 0x2143)", [_rgb(TT)])
_dev(0x264A, 0x2144, "Thermaltake Riing Trio (PID 0x2144)", [_rgb(TT)])
_dev(0x264A, 0x2145, "Thermaltake Riing Trio (PID 0x2145)", [_rgb(TT)])

NOTE = "A matching USB ID alone does not prove your unit speaks the same protocol; check the project's notes."

USB_IDS_PATHS = ("/usr/share/hwdata/usb.ids", "/usr/share/misc/usb.ids", "/usr/share/usb.ids",
                 "/var/lib/usbutils/usb.ids", "/usr/local/share/hwdata/usb.ids")

ODB_API = "https://opendevicedb.org/api"


def parse_id(text: str) -> tuple[int, int]:
    """'1e71:170e', '0x1e71:0x170e', '1e71 170e' or 'ID 1e71:170e' (lsusb) -> (0x1e71, 0x170e)."""
    m = re.fullmatch(
        r"\s*(?:ID\s+)?(?:0x)?([0-9a-fA-F]{1,4})\s*[:\s]\s*(?:0x)?([0-9a-fA-F]{1,4})\s*",
        text,
        re.IGNORECASE,
    )
    if not m:
        raise ValueError(
            f"not a VID:PID: {text!r}. Expected a USB ID like 1e71:170e (from lsusb), "
            f"or a path to a pcap/pcapng capture"
        )
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
