# Known devices

`usb-rea lookup <VID:PID>` (or a capture file) checks this offline table before you start
capturing. Each row is a USB ID whose protocol an open-source project already implements
or documents. The IDs were copied from those projects' public source files (cited in
`src/usb_rea/lookup.py` and in the links below), not from private captures.

This page is the same table the CLI uses. An unknown ID stays unknown. `--online` also
asks [OpenDeviceDB](https://opendevicedb.org) (only the ID is sent). OpenRGB in particular
supports many more devices than the curated set here; `--online` often lists it when the
offline table does not.

A matching USB ID alone does not prove your unit speaks the same protocol; check the project's notes.

Generic or reused IDs (a WCH serial bridge, a Linux USB gadget default, a Winbond HID
controller) are included when a project documents them, with a **limits** note. A match
is a hint, not proof that your unit speaks the same protocol.

## How to look one up

```bash
usb-rea lookup 1e71:170e
usb-rea lookup "ID 1e71:170e"    # lsusb form
usb-rea lookup capture.pcapng    # every device whose descriptor is in the capture
```

The MCP tool is `lookup_device`.


The table currently has **267** USB IDs.

## liquidctl

| VID:PID | Device | Projects | Limits |
| --- | --- | --- | --- |
| `0416:7395` | Lian Li GA II LCD | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/ga2_lcd.py) |  |
| `048d:5702` | Gigabyte RGB Fusion 2.0 5702 Controller | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/rgb_fusion2.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/GigabyteRGBFusion2USBController/GigabyteRGBFusion2USBControllerDetect.cpp) (RGB lighting) |  |
| `048d:8297` | Gigabyte RGB Fusion 2.0 8297 Controller | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/rgb_fusion2.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/GigabyteRGBFusion2USBController/GigabyteRGBFusion2USBControllerDetect.cpp) (RGB lighting) |  |
| `0b05:1887` | ASUS Ryuo I 240 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asus_ryuo.py) |  |
| `0b05:18f3` | ASUS Aura LED Controller | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/aura_led.py) | liquidctl notes this ID is not fully supported yet |
| `0b05:1939` | ASUS Aura LED Controller | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/aura_led.py) | liquidctl notes this ID is not fully supported yet |
| `0b05:1988` | ASUS Ryujin II 360 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asus_ryujin.py) |  |
| `0b05:19af` | ASUS Aura LED Controller | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/aura_led.py) |  |
| `0b05:1aa2` | ASUS Ryujin III 360 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asus_ryujin.py) |  |
| `0b05:1ada` | ASUS Ryujin III White | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asus_ryujin.py) |  |
| `0b05:1ade` | ASUS Ryujin III EVA | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asus_ryujin.py) |  |
| `0b05:1bcb` | ASUS Ryujin III Extreme | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asus_ryujin.py) |  |
| `0c70:f00a` | Aquacomputer Farbwerk | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/aquacomputer.py) |  |
| `0c70:f00d` | Aquacomputer Quadro | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/aquacomputer.py) |  |
| `0c70:f00e` | Aquacomputer D5 Next | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/aquacomputer.py) |  |
| `0c70:f010` | Aquacomputer Farbwerk 360 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/aquacomputer.py) |  |
| `0c70:f011` | Aquacomputer Octo | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/aquacomputer.py) |  |
| `0cf2:7750` | Lian Li Uni SL | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/lianli_uni.py) |  |
| `0cf2:a100` | Lian Li Uni SL | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/lianli_uni.py) |  |
| `0cf2:a101` | Lian Li Uni AL | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/lianli_uni.py) |  |
| `0cf2:a102` | Lian Li Uni SL-Infinity | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/lianli_uni.py) |  |
| `0cf2:a103` | Lian Li Uni SL V2 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/lianli_uni.py) |  |
| `0cf2:a104` | Lian Li Uni AL V2 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/lianli_uni.py) |  |
| `0cf2:a105` | Lian Li Uni SL V2 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/lianli_uni.py) |  |
| `0db0:b130` | MSI MPG Coreliquid K360 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/msi.py) |  |
| `0db0:ca00` | Suspected MSI MPG Coreliquid | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/msi.py) | liquidctl only drives it with the experimental_coreliquid_cooler unsafe flag |
| `0db0:ca02` | Suspected MSI MPG Coreliquid | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/msi.py) | liquidctl only drives it with the experimental_coreliquid_cooler unsafe flag |
| `1b1c:0c02` | Corsair Hydro H80i GT | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asetek.py) |  |
| `1b1c:0c03` | Corsair Hydro H100i GTX | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asetek.py) |  |
| `1b1c:0c04` | Corsair H110i GT | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/coolit.py) |  |
| `1b1c:0c07` | Corsair Hydro H110i GTX | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asetek.py) |  |
| `1b1c:0c08` | Corsair Hydro H80i v2 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asetek.py) |  |
| `1b1c:0c09` | Corsair Hydro H100i v2 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asetek.py) |  |
| `1b1c:0c0a` | Corsair Hydro H115i | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asetek.py) |  |
| `1b1c:0c0b` | Corsair Lighting Node Pro | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/commander_pro.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairLightingNodeController/CorsairLightingNodeControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c10` | Corsair Commander Pro | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/commander_pro.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairLightingNodeController/CorsairLightingNodeControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c12` | Corsair Hydro H150i Pro | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asetek_pro.py) |  |
| `1b1c:0c13` | Corsair Hydro H115i Pro | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asetek_pro.py) |  |
| `1b1c:0c15` | Corsair Hydro H100i Pro | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asetek_pro.py) |  |
| `1b1c:0c17` | Corsair Hydro H115i Platinum | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c18` | Corsair Hydro H100i Platinum | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting), [usb-rea case study](https://github.com/emirmrkaljevic/usb-rea/blob/main/docs/case-study-hydro-platinum.md) (CRC8 and sequence counter recovered) |  |
| `1b1c:0c19` | Corsair Hydro H100i Platinum SE | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c1a` | Corsair Lighting Node Core | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/commander_pro.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairLightingNodeController/CorsairLightingNodeControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c1c` | Corsair Commander Core | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/commander_core.py) | liquidctl marks this match as broken |
| `1b1c:0c20` | Corsair Hydro H100i Pro XT | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c21` | Corsair Hydro H115i Pro XT | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c22` | Corsair Hydro H150i Pro XT | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c29` | Corsair Hydro H60i Pro XT | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c2a` | Corsair Commander Core XT | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/commander_core.py) | liquidctl marks this match as broken |
| `1b1c:0c32` | Corsair Commander ST | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/commander_core.py) | liquidctl marks this match as broken |
| `1b1c:0c35` | Corsair iCUE H100i Elite RGB | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c36` | Corsair iCUE H115i Elite RGB | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c37` | Corsair iCUE H150i Elite RGB | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c40` | Corsair iCUE H100i Elite RGB (White) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c41` | Corsair iCUE H150i Elite RGB (White) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:1c05` | Corsair HX750i | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/corsair_hid_psu.py) |  |
| `1b1c:1c06` | Corsair HX850i | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/corsair_hid_psu.py) |  |
| `1b1c:1c07` | Corsair HX1000i | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/corsair_hid_psu.py) |  |
| `1b1c:1c08` | Corsair HX1200i | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/corsair_hid_psu.py) |  |
| `1b1c:1c0a` | Corsair RM650i | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/corsair_hid_psu.py) |  |
| `1b1c:1c0b` | Corsair RM750i | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/corsair_hid_psu.py) |  |
| `1b1c:1c0c` | Corsair RM850i | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/corsair_hid_psu.py) |  |
| `1b1c:1c0d` | Corsair RM1000i | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/corsair_hid_psu.py) |  |
| `1b1c:1c1e` | Corsair HX1000i (2022) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/corsair_hid_psu.py) |  |
| `1b1c:1c1f` | Corsair HX1500i | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/corsair_hid_psu.py) |  |
| `1b1c:1c23` | Corsair HX1200i ATX 3.1 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/corsair_hid_psu.py) |  |
| `1b1c:1c27` | Corsair HX1200i ATX 3.1 #2 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/corsair_hid_psu.py) |  |
| `1b1c:1d00` | Corsair Obsidian 1000D | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/commander_pro.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairLightingNodeController/CorsairLightingNodeControllerDetect.cpp) (RGB lighting) |  |
| `1e71:170e` | NZXT Kraken X (X42, X52, X62 or X72) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/kraken2.py) (fan/pump duty, lighting, status), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTKrakenController/NZXTKrakenControllerDetect.cpp) (RGB lighting), [usb-rea validation](https://github.com/emirmrkaljevic/usb-rea/blob/main/docs/VALIDATION.md) (fan duty command recovered byte for byte) |  |
| `1e71:1711` | NZXT Grid+ V3 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py) |  |
| `1e71:1714` | NZXT Smart Device (V1) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py) |  |
| `1e71:1715` | NZXT Kraken M22 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/kraken2.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTKrakenController/NZXTKrakenControllerDetect.cpp) (RGB lighting) |  |
| `1e71:2001` | NZXT HUE 2 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:2002` | NZXT HUE 2 Ambient | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:2006` | NZXT Smart Device V2 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:2007` | NZXT Kraken X (X53, X63 or X73) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/kraken3.py) |  |
| `1e71:2009` | NZXT RGB & Fan Controller | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:200d` | NZXT Smart Device V2 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:200e` | NZXT RGB & Fan Controller | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:200f` | NZXT Smart Device V2 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:2010` | NZXT RGB & Fan Controller | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:2011` | NZXT RGB & Fan Controller (3+6 channels) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:2012` | NZXT 2023 RGB Controller | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:2014` | NZXT Kraken X (X53, X63 or X73) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/kraken3.py) |  |
| `1e71:2015` | NZXT H1 V2 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py) |  |
| `1e71:2019` | NZXT RGB & Fan Controller (3+6 channels) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:201f` | NZXT RGB & Fan Controller (3+6 channels) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:2020` | NZXT RGB & Fan Controller (3+6 channels) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:2021` | NZXT 2023 RGB Controller | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/smart_device.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:2022` | NZXT Control Hub | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/control_hub.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:3008` | NZXT Kraken Z (Z53, Z63 or Z73) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/kraken3.py) (includes the 320x320 LCD) |  |
| `1e71:300c` | NZXT Kraken 2023 Elite | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/kraken3.py) | liquidctl marks this match as broken |
| `1e71:300e` | NZXT Kraken 2023 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/kraken3.py) |  |
| `1e71:3012` | NZXT Kraken 2024 Elite RGB | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/kraken3.py), [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:3014` | NZXT Kraken 2024 Plus | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/kraken3.py) |  |
| `2433:b200` | Asetek 690LC (EVGA CLC or NZXT Kraken X, depending on the driver) | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/asetek.py) | the same ID is used by more than one Asetek 690LC rebrand; liquidctl has separate drivers |
| `7793:2500` | NZXT E850 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/nzxt_epsu.py) |  |
| `7793:5911` | NZXT E500 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/nzxt_epsu.py) |  |
| `7793:5912` | NZXT E650 | [liquidctl](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/nzxt_epsu.py) |  |

## rivalcfg

| VID:PID | Device | Projects | Limits |
| --- | --- | --- | --- |
| `1038:1362` | SteelSeries Sensei [RAW] Diablo III Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/sensei_raw.py) (DPI, polling rate, lighting) |  |
| `1038:1366` | SteelSeries Kinzu v2 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/kinzuv2.py) (DPI, polling rate, lighting) |  |
| `1038:1369` | SteelSeries Sensei [RAW] | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/sensei_raw.py) (DPI, polling rate, lighting) |  |
| `1038:136d` | SteelSeries Sensei [RAW] Guild Wars 2 Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/sensei_raw.py) (DPI, polling rate, lighting) |  |
| `1038:136f` | SteelSeries Sensei [RAW] CoD Black Ops II Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/sensei_raw.py) (DPI, polling rate, lighting) |  |
| `1038:1378` | SteelSeries Kinzu v2 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/kinzuv2.py) (DPI, polling rate, lighting) |  |
| `1038:137a` | SteelSeries Kana v2 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/kanav2.py) (DPI, polling rate, lighting) |  |
| `1038:1380` | SteelSeries Sensei [RAW] World of Tanks Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/sensei_raw.py) (DPI, polling rate, lighting) |  |
| `1038:1384` | SteelSeries Rival | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival300.py) (DPI, polling rate, lighting) |  |
| `1038:1390` | SteelSeries Sensei [RAW] Heroes of the Storm Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/sensei_raw.py) (DPI, polling rate, lighting) |  |
| `1038:1392` | SteelSeries Rival Dota 2 Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival300.py) (DPI, polling rate, lighting) |  |
| `1038:1394` | SteelSeries Rival 300 CS:GO Fade Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival300.py) (DPI, polling rate, lighting) |  |
| `1038:1700` | SteelSeries Rival 700 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival700.py) (DPI, polling rate, lighting) |  |
| `1038:1702` | SteelSeries Rival 100 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival100.py) (DPI, polling rate, lighting), [usb-rea validation](https://github.com/emirmrkaljevic/usb-rea/blob/main/docs/VALIDATION.md) (DPI/polling lookup tables recovered) |  |
| `1038:1704` | SteelSeries Rival 95 PC Bang | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival95.py) (DPI, polling rate, lighting) |  |
| `1038:1706` | SteelSeries Rival 95 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival95.py) (DPI, polling rate, lighting) |  |
| `1038:1707` | SteelSeries Rival 95 MSI Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival95.py) (DPI, polling rate, lighting) |  |
| `1038:1708` | SteelSeries Rival 100 PC Bang | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival95.py) (DPI, polling rate, lighting) |  |
| `1038:170a` | SteelSeries Rival 100 (Dell China) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival100.py) (DPI, polling rate, lighting) |  |
| `1038:170b` | SteelSeries Rival 100 Dota 2 Edition (retail) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival100.py) (DPI, polling rate, lighting) |  |
| `1038:170c` | SteelSeries Rival 100 Dota 2 Edition (Lenovo) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival100.py) (DPI, polling rate, lighting) |  |
| `1038:170e` | SteelSeries Rival 500 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival500.py) (DPI, polling rate, lighting) |  |
| `1038:1710` | SteelSeries Rival 300 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival300.py) (DPI, polling rate, lighting) |  |
| `1038:1712` | SteelSeries Rival 300 Fallout 4 Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival300.py) (DPI, polling rate, lighting) |  |
| `1038:1714` | SteelSeries Rival 300 Acer Predator Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival300.py) (DPI, polling rate, lighting) |  |
| `1038:1716` | SteelSeries Rival 300 CS:GO Fade Edition (stm32) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival300.py) (DPI, polling rate, lighting) |  |
| `1038:1718` | SteelSeries Rival 300 HP OMEN Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival300.py) (DPI, polling rate, lighting) |  |
| `1038:171a` | SteelSeries Rival 300 CS:GO Hyper Beast Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival300.py) (DPI, polling rate, lighting) |  |
| `1038:171c` | SteelSeries Rival 300 Evil Geniuses Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival300.py) (DPI, polling rate, lighting) |  |
| `1038:171e` | SteelSeries Rival 310 CS:GO Howl Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival310.py) (DPI, polling rate, lighting) |  |
| `1038:1720` | SteelSeries Rival 310 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival310.py) (DPI, polling rate, lighting) |  |
| `1038:1722` | SteelSeries Sensei 310 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/sensei310.py) (DPI, polling rate, lighting) |  |
| `1038:1724` | SteelSeries Rival 600 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival600.py) (DPI, polling rate, lighting) |  |
| `1038:1726` | SteelSeries Rival 650 Wireless (2.4 GHz wireless mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival650.py) (DPI, polling rate, lighting) |  |
| `1038:1729` | SteelSeries Rival 110 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival110.py) (DPI, polling rate, lighting) |  |
| `1038:172b` | SteelSeries Rival 650 Wireless (wired mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival650.py) (DPI, polling rate, lighting) |  |
| `1038:172e` | SteelSeries Rival 600 Dota 2 Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival600.py) (DPI, polling rate, lighting) |  |
| `1038:1730` | SteelSeries Rival 710 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival700.py) (DPI, polling rate, lighting) |  |
| `1038:1736` | SteelSeries Rival 310 PUBG Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival310.py) (DPI, polling rate, lighting) |  |
| `1038:1810` | SteelSeries Rival 300S | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival300s.py) (DPI, polling rate, lighting) |  |
| `1038:1814` | SteelSeries Rival 105 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival100.py) (DPI, polling rate, lighting) |  |
| `1038:1816` | SteelSeries Rival 106 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival110.py) (DPI, polling rate, lighting) |  |
| `1038:1824` | SteelSeries Rival 3 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival3.py) (DPI, polling rate, lighting) |  |
| `1038:182a` | SteelSeries Prime Rainbow 6 Siege Black Ice Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/prime.py) (DPI, polling rate, lighting) |  |
| `1038:182c` | SteelSeries Prime+ | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/prime_plus.py) (DPI, polling rate, lighting) |  |
| `1038:182e` | SteelSeries Prime | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/prime.py) (DPI, polling rate, lighting) |  |
| `1038:1830` | SteelSeries Rival 3 Wireless (2.4 GHz mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival3_wireless.py) (DPI, polling rate, lighting) |  |
| `1038:1832` | SteelSeries Sensei TEN | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/sensei_ten.py) (DPI, polling rate, lighting) |  |
| `1038:1834` | SteelSeries Sensei TEN CS:GO Neon Rider Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/sensei_ten.py) (DPI, polling rate, lighting) |  |
| `1038:1836` | SteelSeries Aerox 3 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox3.py) (DPI, polling rate, lighting) |  |
| `1038:1838` | SteelSeries Aerox 3 Wireless (2.4 GHz wireless mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox3_wireless_wireless.py) (DPI, polling rate, lighting) |  |
| `1038:183a` | SteelSeries Aerox 3 Wireless (wired mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox3_wireless_wired.py) (DPI, polling rate, lighting) |  |
| `1038:183c` | SteelSeries Rival 5 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival5.py) (DPI, polling rate, lighting) |  |
| `1038:183e` | SteelSeries Rival 5 Destiny Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival5.py) (DPI, polling rate, lighting) |  |
| `1038:1840` | SteelSeries Prime Wireless (2.4 GHz wireless mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/prime_wireless_wireless.py) (DPI, polling rate, lighting) |  |
| `1038:1842` | SteelSeries Prime Wireless (wired mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/prime_wireless_wired.py) (DPI, polling rate, lighting) |  |
| `1038:1848` | SteelSeries Prime Mini Wireless (2.4 GHz wireless mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/prime_wireless_wireless.py) (DPI, polling rate, lighting) |  |
| `1038:184a` | SteelSeries Prime Mini Wireless (wired mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/prime_wireless_wired.py) (DPI, polling rate, lighting) |  |
| `1038:184c` | SteelSeries Rival 3 (firmware v0.37.0.0) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival3.py) (DPI, polling rate, lighting) |  |
| `1038:184d` | SteelSeries Prime Mini | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/prime_mini.py) (DPI, polling rate, lighting) |  |
| `1038:1850` | SteelSeries Aerox 5 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox5.py) (DPI, polling rate, lighting) |  |
| `1038:1852` | SteelSeries Aerox 5 Wireless (2.4 GHz wireless mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox5_wireless_wireless.py) (DPI, polling rate, lighting) |  |
| `1038:1854` | SteelSeries Aerox 5 Wireless (wired mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox5_wireless_wired.py) (DPI, polling rate, lighting) |  |
| `1038:1856` | SteelSeries Prime CS:GO Neo Noir Edition | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/prime.py) (DPI, polling rate, lighting) |  |
| `1038:1858` | SteelSeries Aerox 9 Wireless (2.4 GHz wireless mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox9_wireless_wireless.py) (DPI, polling rate, lighting) |  |
| `1038:185a` | SteelSeries Aerox 9 Wireless (wired mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox9_wireless_wired.py) (DPI, polling rate, lighting) |  |
| `1038:185c` | SteelSeries Aerox 5 Wireless Destiny 2 Edition (2.4 GHz wireless mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox5_wireless_wireless.py) (DPI, polling rate, lighting) |  |
| `1038:185e` | SteelSeries Aerox 5 Wireless Destiny 2 Edition (wired mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox5_wireless_wired.py) (DPI, polling rate, lighting) |  |
| `1038:1860` | SteelSeries Aerox 5 Wireless Diablo IV Edition (2.4 GHz wireless mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox5_wireless_wireless.py) (DPI, polling rate, lighting) |  |
| `1038:1862` | SteelSeries Aerox 5 Wireless Diablo IV Edition (wired mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox5_wireless_wired.py) (DPI, polling rate, lighting) |  |
| `1038:1870` | SteelSeries Rival 3 Gen 2 | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival3_gen2.py) (DPI, polling rate, lighting) |  |
| `1038:1872` | SteelSeries Rival 3 Wireless Gen 2 (2.4 GHz mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/rival3_wireless_gen2.py) (DPI, polling rate, lighting) |  |
| `1038:1874` | SteelSeries Aerox 9 Wireless WOW Edition (2.4 GHz wireless mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox9_wireless_wireless.py) (DPI, polling rate, lighting) |  |
| `1038:1876` | SteelSeries Aerox 9 Wireless WOW Edition (wired mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox9_wireless_wired.py) (DPI, polling rate, lighting) |  |
| `1038:1878` | SteelSeries Aerox 3 Wireless CS2 Dragon Lore Edition (2.4 GHz wireless mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox3_wireless_wireless.py) (DPI, polling rate, lighting) |  |
| `1038:187a` | SteelSeries Aerox 3 Wireless CS2 Dragon Lore Edition (wired mode) | [rivalcfg](https://github.com/flozz/rivalcfg/blob/master/rivalcfg/devices/aerox3_wireless_wired.py) (DPI, polling rate, lighting) |  |

## turing-smart-screen-python

| VID:PID | Device | Projects | Limits |
| --- | --- | --- | --- |
| `0525:a4a7` | Turing / UsbPCMonitor screen (rev C, awake) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (rev C serial protocol) | this is a common Linux USB gadget ID (Netchip); unrelated gadgets use it too |
| `1a86:5722` | Turing Smart Screen 3.5" (rev A) / XuanFang (rev B) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (serial protocol for revisions A and B) | generic WCH serial bridge ID; the project tells revisions apart by the USB serial number (USB35INCHIPSV2 is rev A, 2017-2-25 is rev B), and unrelated devices use this ID too |
| `1a86:ca21` | Turing / UsbPCMonitor 7-inch class screen (rev C, sleeping) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (rev C serial protocol) | the project also looks at serial numbers USB7INCH, CT21INCH and CT88INCH |
| `1a86:fe0c` | WeAct Studio USB display (rev A or B) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (WeAct A/B serial protocol) | the project tells revisions apart by the USB serial number (AB... is WeAct A, AD... is WeAct B) |
| `1cbe:0028` | Turing 2.8-inch round (USB) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (native USB protocol, not serial) |  |
| `1cbe:0046` | Turing 4.6-inch (USB) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (native USB protocol, not serial) |  |
| `1cbe:0050` | Turing 5.2-inch (USB) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (native USB protocol, not serial) |  |
| `1cbe:0080` | Turing 8.0-inch (USB) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (native USB protocol, not serial) |  |
| `1cbe:0088` | Turing 8.8-inch (USB) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (native USB protocol, not serial) |  |
| `1cbe:0092` | Turing 9.2-inch (USB) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (native USB protocol, not serial) |  |
| `1cbe:0123` | Turing 12.3-inch (USB) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (native USB protocol, not serial) |  |
| `1d6b:0106` | Turing / UsbPCMonitor screen (rev C, awake) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (rev C serial protocol) | Linux Foundation gadget ID; unrelated USB gadgets use it too |
| `1d6b:0121` | Turing / UsbPCMonitor screen (rev C, awake) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (rev C serial protocol) | Linux Foundation gadget ID; unrelated USB gadgets use it too |
| `454d:4e41` | Turing-compatible LCD (rev D) | [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (rev D serial protocol) |  |

## linux-thermalright-lcd-control

| VID:PID | Device | Projects | Limits |
| --- | --- | --- | --- |
| `0402:3922` | Thermalright Frozen Warframe LCD (320x320) | [linux-thermalright-lcd-control](https://github.com/rejeb/linux-thermalright-lcd-control/blob/master/src/thermalright_lcd_control/device_controller/display/device_0402_3922.py) (USB mass-storage (SCSI BOT) display protocol) |  |
| `0416:5302` | Thermalright LCD (ChiZhu, 320x240, HID) | [linux-thermalright-lcd-control](https://github.com/rejeb/linux-thermalright-lcd-control) | Winbond/Nuvoton generic ID used by other products as well |
| `0416:5406` | Winbond LCD (SCSI) | [linux-thermalright-lcd-control](https://github.com/rejeb/linux-thermalright-lcd-control/blob/master/src/thermalright_lcd_control/device_controller/display/probe_registry/0416x5406.yaml) (USB mass-storage (SCSI) transport) | Winbond/Nuvoton generic ID used by other products as well |
| `0416:5408` | Thermalright LCD (LY) | [linux-thermalright-lcd-control](https://github.com/rejeb/linux-thermalright-lcd-control) |  |
| `0416:5409` | Thermalright LCD (LY) | [linux-thermalright-lcd-control](https://github.com/rejeb/linux-thermalright-lcd-control) |  |
| `0416:8001` | Winbond LED Controller (Thermalright LED display) | [linux-thermalright-lcd-control](https://github.com/rejeb/linux-thermalright-lcd-control/blob/master/src/thermalright_lcd_control/common/supported_devices.py) (LED controller; style resolved from the HID handshake) | Winbond/Nuvoton generic ID used by other products as well |
| `0418:5303` | ALi LCD (HID type 3) | [linux-thermalright-lcd-control](https://github.com/rejeb/linux-thermalright-lcd-control/blob/master/src/thermalright_lcd_control/device_controller/display/probe_registry/0418x5303.yaml) (found by the HID type 3 handshake probe) |  |
| `0418:5304` | Thermalright LCD (ALi, 480x480, HID type 3) | [linux-thermalright-lcd-control](https://github.com/rejeb/linux-thermalright-lcd-control/blob/master/src/thermalright_lcd_control/device_controller/display/hid_devices.py) (HID display protocol, F5-prefix handshake) |  |
| `87ad:70db` | Thermalright LCD (ChiZhu, 320/480/640 variants) | [linux-thermalright-lcd-control](https://github.com/rejeb/linux-thermalright-lcd-control) |  |
| `87cd:70db` | Thermalright LCD (SCSI) | [linux-thermalright-lcd-control](https://github.com/rejeb/linux-thermalright-lcd-control/blob/master/src/thermalright_lcd_control/device_controller/display/probe_registry/87CDx70DB.yaml) (USB mass-storage (SCSI) transport) |  |

## OpenRGB (curated)

Only IDs that are not already covered by liquidctl (plus a curated set of Thermaltake Riing controllers and Cooler Master ARGB/RGB hubs). OpenRGB also appears as a second project on some liquidctl rows where both implement the same ID.

| VID:PID | Device | Projects | Limits |
| --- | --- | --- | --- |
| `0414:a100` | Gigabyte RGB Fusion 2 USB | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/GigabyteRGBFusion2USBController/GigabyteRGBFusion2USBControllerDetect.cpp) (RGB lighting) |  |
| `048d:5711` | Gigabyte RGB Fusion 2 USB | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/GigabyteRGBFusion2USBController/GigabyteRGBFusion2USBControllerDetect.cpp) (RGB lighting) |  |
| `048d:8950` | Gigabyte RGB Fusion 2 USB | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/GigabyteRGBFusion2USBController/GigabyteRGBFusion2USBControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c1e` | Corsair LS100 | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairLightingNodeController/CorsairLightingNodeControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c23` | Corsair LT100 | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairLightingNodeController/CorsairLightingNodeControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:0c2d` | Corsair Hydro H100i Pro XT V2 | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumControllerDetect.cpp) (RGB lighting) |  |
| `1b1c:1d04` | Corsair SPEC OMEGA RGB | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CorsairLightingNodeController/CorsairLightingNodeControllerDetect.cpp) (RGB lighting) |  |
| `1e71:2005` | NZXT motherboard RGB device | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:200b` | NZXT motherboard RGB device | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `1e71:201b` | NZXT RGB & Fan Controller | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/NZXTHue2Controller/NZXTHue2ControllerDetect.cpp) (RGB lighting) |  |
| `2516:004f` | Cooler Master RGB | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CoolerMasterController/CoolerMasterControllerDetect.cpp) (RGB lighting) |  |
| `2516:0173` | Cooler Master ARGB Gen 2 A1 | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CoolerMasterController/CoolerMasterControllerDetect.cpp) (RGB lighting) |  |
| `2516:01c9` | Cooler Master ARGB Gen 2 A1 V2 | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CoolerMasterController/CoolerMasterControllerDetect.cpp) (RGB lighting) |  |
| `2516:01cb` | Cooler Master ARGB Gen 2 A1 Mini | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CoolerMasterController/CoolerMasterControllerDetect.cpp) (RGB lighting) |  |
| `2516:1000` | Cooler Master Small ARGB | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CoolerMasterController/CoolerMasterControllerDetect.cpp) (RGB lighting) |  |
| `2516:1011` | Cooler Master ARGB | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/CoolerMasterController/CoolerMasterControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fa5` | Thermaltake Riing (PID 0x1FA5) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fa6` | Thermaltake Riing (PID 0x1FA6) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fa7` | Thermaltake Riing (PID 0x1FA7) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fa8` | Thermaltake Riing (PID 0x1FA8) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fa9` | Thermaltake Riing (PID 0x1FA9) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1faa` | Thermaltake Riing (PID 0x1FAA) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fab` | Thermaltake Riing (PID 0x1FAB) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fac` | Thermaltake Riing (PID 0x1FAC) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fad` | Thermaltake Riing (PID 0x1FAD) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fae` | Thermaltake Riing (PID 0x1FAE) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1faf` | Thermaltake Riing (PID 0x1FAF) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fb0` | Thermaltake Riing (PID 0x1FB0) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fb1` | Thermaltake Riing (PID 0x1FB1) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fb2` | Thermaltake Riing (PID 0x1FB2) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fb3` | Thermaltake Riing (PID 0x1FB3) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fb4` | Thermaltake Riing (PID 0x1FB4) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:1fb5` | Thermaltake Riing (PID 0x1FB5) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2135` | Thermaltake Riing Trio (PID 0x2135) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2136` | Thermaltake Riing Trio (PID 0x2136) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2137` | Thermaltake Riing Trio (PID 0x2137) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2138` | Thermaltake Riing Trio (PID 0x2138) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2139` | Thermaltake Riing Trio (PID 0x2139) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:213a` | Thermaltake Riing Trio (PID 0x213A) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:213b` | Thermaltake Riing Trio (PID 0x213B) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:213c` | Thermaltake Riing Trio (PID 0x213C) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:213d` | Thermaltake Riing Trio (PID 0x213D) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:213e` | Thermaltake Riing Trio (PID 0x213E) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:213f` | Thermaltake Riing Trio (PID 0x213F) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2141` | Thermaltake Riing Trio (PID 0x2141) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2142` | Thermaltake Riing Trio (PID 0x2142) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2143` | Thermaltake Riing Trio (PID 0x2143) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2144` | Thermaltake Riing Trio (PID 0x2144) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2145` | Thermaltake Riing Trio (PID 0x2145) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2260` | Thermaltake Riing Quad (PID 0x2260) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2261` | Thermaltake Riing Quad (PID 0x2261) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2262` | Thermaltake Riing Quad (PID 0x2262) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2263` | Thermaltake Riing Quad (PID 0x2263) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2264` | Thermaltake Riing Quad (PID 0x2264) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2265` | Thermaltake Riing Quad (PID 0x2265) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2266` | Thermaltake Riing Quad (PID 0x2266) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2267` | Thermaltake Riing Quad (PID 0x2267) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2268` | Thermaltake Riing Quad (PID 0x2268) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2269` | Thermaltake Riing Quad (PID 0x2269) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:226a` | Thermaltake Riing Quad (PID 0x226A) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:226b` | Thermaltake Riing Quad (PID 0x226B) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:226c` | Thermaltake Riing Quad (PID 0x226C) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:226d` | Thermaltake Riing Quad (PID 0x226D) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:226e` | Thermaltake Riing Quad (PID 0x226E) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:226f` | Thermaltake Riing Quad (PID 0x226F) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:2270` | Thermaltake Riing Quad (PID 0x2270) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |
| `264a:232b` | Thermaltake Riing Quad (PID 0x232B) | [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Controllers/ThermaltakeRiingController/ThermaltakeRiingControllerDetect.cpp) (RGB lighting) |  |

## usb-rea case studies only

| VID:PID | Device | Projects | Limits |
| --- | --- | --- | --- |
| `0b05:1c7b` | ASUS TUF Gaming LC III LCD | [usb-rea case study](https://github.com/emirmrkaljevic/usb-rea/blob/main/docs/case-study-asus-tuf-lc3.md) (brightness command and JPEG stream from one real capture; not a full driver) |  |
