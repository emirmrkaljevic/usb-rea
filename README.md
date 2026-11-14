# usb-rea

<p align="center"><a href="https://skintoscan.com/#packages"><img src=".github/assets/skintoscan-support.svg" width="684" alt="Support my open-source work: get a SkinToScan pack"></a><br><sub>If you find this useful, you can support me by getting a SkinToScan pack, my other project. It's a one-time purchase that directly funds my open-source work.</sub></p>
<p align="center"><a href="https://skintoscan.com/checkout/?add-to-cart=138"><img src=".github/assets/skintoscan-pack-1.svg" width="220" alt="Buy Single Picture Check, €4.49"></a> <a href="https://skintoscan.com/checkout/?add-to-cart=139"><img src=".github/assets/skintoscan-pack-5.svg" width="220" alt="Buy 5 Picture Pack, €19.99 (popular)"></a> <a href="https://skintoscan.com/checkout/?add-to-cart=140"><img src=".github/assets/skintoscan-pack-15.svg" width="220" alt="Buy 15 Picture Pack, €54.99"></a></p>

<!-- mcp-name: io.github.emirmrkaljevic/usb-rea -->

[![ci](https://github.com/emirmrkaljevic/usb-rea/actions/workflows/ci.yml/badge.svg)](https://github.com/emirmrkaljevic/usb-rea/actions/workflows/ci.yml) ![license](https://img.shields.io/badge/license-MIT-blue) [![usb-rea MCP server](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea/badges/score.svg)](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea)

usb-rea reads a USB capture (pcap or pcapng, from usbmon or USBPcap) and does the step after Wireshark: it infers the command and protocol structure from labelled actions, then writes a Markdown report and a standalone pyusb driver. I built it for gadgets that only ship a Windows vendor app, such as a case LCD, an RGB controller, a mouse or a "smart" lamp. No hardware is needed to try it.

![usb-rea demo: capture labelled clicks, get the protocol and a working driver](docs/demo.gif)

From captures of the NZXT Kraken X (1e71:170e) fan command, it recovers `02 4d <channel> 00 <duty>` byte for byte, as liquidctl's `kraken2.py` sends it, and the generated driver emits identical packets for duty values it never saw. The same holds for the SteelSeries Rival 100 DPI, polling and RGB tables from rivalcfg. Those checks run in CI; details are in [validation](docs/VALIDATION.md).

## Install

```sh
pip install usb-rea
```

## Example

```sh
usb-rea demo --device fan
```

```
mode         100%  0x5a | counter (+1 per message) | 0x30 | lookup 1→0x11, 2→0x22, 3→0x47 | 0x00 | 0x00 | u16le crc16_modbus(bytes[0:6])
fan          100%  0x5a | counter (+1 per message) | 0x10 | u16be round(value * 1 + 0) | 0x00 | u16le crc16_modbus(bytes[0:6])
color        100%  0x5a | counter (+1 per message) | 0x20 | RGB bytes | u16le crc16_modbus(bytes[0:6])
  color only sent while mode 3: the driver sets it first
```

It writes a synthetic capture of a fan controller, recovers the protocol and the replies, and writes `report.md` (every claim linked to Wireshark frame numbers) plus a working pyusb driver. `--device lamp` is a simpler 8-bit device; `--device lcd` is a pump cap screen; `--device dial` shows 32-bit values and packed bitfields.

On a real device, label each click in the vendor app, then infer:

```sh
sudo modprobe usbmon
usb-rea capture start -o lamp.pcapng
usb-rea mark -m lamp.pcapng.actions.json "brightness 0%"   # then click it; 3+ values per setting
usb-rea capture stop
usb-rea report lamp.pcapng -o report.md
usb-rea scaffold lamp.pcapng -o lamp_driver.py
```

Captured on Windows with USBPcap and no markers? List the actions in order and usb-rea splits the traffic at the pauses. The full CLI, including markers, replies, handshakes, image streams and HID, is in [usage](docs/usage.md).

Before you capture, `usb-rea lookup 1e71:170e` (or the `ID 1e71:170e` form from `lsusb`) checks a VID:PID against devices whose protocol an open-source project already implements. The offline table is in [known devices](docs/known-devices.md).

## Limitations

Status: alpha (v0.7.14, [on PyPI](https://pypi.org/project/usb-rea/)). It is validated on synthetic devices, on protocols documented by liquidctl and rivalcfg, on public Wireshark captures, and on a real AIO cooler LCD capture a user shared. Linear fits must survive leave-one-out cross-checks; otherwise usb-rea falls back to a lookup table and says so. A matching USB ID alone does not prove your unit speaks the same protocol.

How this differs from Wireshark is in the [FAQ](docs/faq.md).

Reverse engineering for interoperability is permitted (EU Directive 2009/24/EC Art. 6, US DMCA §1201(f)). usb-rea only analyzes traffic of devices you own and never redistributes vendor code.

Have a Windows-only device? [Open a device request](https://github.com/emirmrkaljevic/usb-rea/discussions/1) with a capture and I will run it and publish the result.

## Docs

- [Usage: capture, markers, inference and the generated driver](docs/usage.md)
- [Capturing on Windows with USBPcap](docs/capture-windows.md)
- [MCP server](docs/mcp.md)
- [How is this different from Wireshark?](docs/faq.md)
- [Known devices](docs/known-devices.md)
- [Validation](docs/VALIDATION.md)
- Case studies: [Corsair Hydro Platinum](docs/case-study-hydro-platinum.md), [ASUS TUF LC III LCD](docs/case-study-asus-tuf-lc3.md)

MCP Registry name: `io.github.emirmrkaljevic/usb-rea`

## License

MIT
